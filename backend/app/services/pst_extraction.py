"""PST extraction: turns a .pst file into a flat "staging" directory of
normalized items (.eml for mail, .vcf for contacts) plus a manifest describing
each one, ready for `services/email_parsing.py` to parse.

Primary path: `pypff` (libpff) walks the folder tree directly and gives real
transport headers for threading. `readpst` (pst-utils) is used for two things
regardless of whether pypff succeeds: contact export (`-c v`, VCard mode is
mature/well-tested in libpst) and as the mail-export fallback if pypff cannot
open the file at all (corrupt/OST-converted PSTs).

Known limitation: calendar (IPM.Appointment / IPM.Schedule.Meeting.*) items
are recognized and staged as their own doc_type, but detailed fields
(start/end/location/attendees) are MAPI *named* properties, whose numeric
property tag is only resolvable per-file via the PST's name-to-id map. That
resolution isn't implemented here — only the item's subject and timestamp are
captured for now. This needs validation against a real Outlook-generated PST
before relying on it for anything beyond "the appointment exists and is
reviewable"; no such fixture was available to test against.
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime
from pathlib import Path

import vobject

from app.services.email_parsing import parse_eml_bytes

logger = logging.getLogger(__name__)

_PR_MESSAGE_CLASS = 0x001A
_PR_ATTACH_LONG_FILENAME = 0x3707
_PR_ATTACH_FILENAME = 0x3704
_PR_ATTACH_MIME_TAG = 0x370E

_PRESERVED_HEADERS = [
    "From",
    "To",
    "Cc",
    "Bcc",
    "Reply-To",
    "Sender",
    "Subject",
    "Date",
    "Message-ID",
    "In-Reply-To",
    "References",
]


class PSTExtractionError(Exception):
    pass


@dataclass
class ManifestEntry:
    id: str
    doc_type: str  # "email" | "contact" | "calendar"
    staged_path: str
    folder_path: str


@dataclass
class ExtractionResult:
    entries: list[ManifestEntry]
    fallback_used: bool


# --- pure / unit-testable helpers -------------------------------------------------


def build_eml_bytes(
    headers: dict[str, str],
    plain_text: str,
    html: str,
    attachments: list[tuple[str, str, bytes]],
) -> bytes:
    """Build RFC822 bytes from already-extracted parts. Only logical headers
    (From/To/Subject/Message-ID/etc, see `_PRESERVED_HEADERS`) are accepted —
    MIME-structural headers are never passed through, since the body/attachments
    here are rebuilt fresh rather than copied from any original MIME structure.
    """
    out = EmailMessage(policy=policy.default)
    for key in _PRESERVED_HEADERS:
        value = headers.get(key)
        if value:
            out[key] = value

    if html:
        out.set_content(plain_text or "")
        out.add_alternative(html, subtype="html")
    else:
        out.set_content(plain_text or "")

    for filename, mime_type, content in attachments:
        maintype, _, subtype = (mime_type or "application/octet-stream").partition("/")
        out.add_attachment(
            content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=filename or "attachment",
        )

    return out.as_bytes()


def manifest_from_mail_export_dir(root_dir: str) -> list[ManifestEntry]:
    """Walk a `readpst -e -r` (or equivalent) output tree and stage every file
    that parses as a plausible email. Non-message files (readpst side artifacts,
    empty files) are skipped rather than raising.
    """
    entries: list[ManifestEntry] = []
    root = Path(root_dir)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size == 0:
            continue
        try:
            raw = path.read_bytes()
            parsed = parse_eml_bytes(raw)
        except Exception:
            continue
        # Python's email parser is lenient enough that arbitrary garbage still
        # yields a non-empty "body" — require actual header signal instead.
        if not (parsed.subject or parsed.sender or parsed.message_id or parsed.recipients_to):
            continue
        folder_path = str(path.parent.relative_to(root))
        entries.append(
            ManifestEntry(
                id=str(uuid.uuid4()),
                doc_type="email",
                staged_path=str(path),
                folder_path="" if folder_path == "." else folder_path,
            )
        )
    return entries


def parse_vcard_contact(raw: bytes | str) -> dict:
    """Parse a single vCard into the contact `structured_metadata` shape."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    card = vobject.readOne(text)

    full_name = getattr(card, "fn", None)
    emails = [e.value for e in getattr(card, "email_list", [])]
    phones = [t.value for t in getattr(card, "tel_list", [])]
    org = getattr(card, "org", None)
    title = getattr(card, "title", None)

    return {
        "full_name": full_name.value if full_name else "",
        "emails": emails,
        "phones": phones,
        "company": ", ".join(org.value)
        if org and isinstance(org.value, list)
        else (org.value if org else ""),
        "title": title.value if title else "",
    }


def manifest_from_contact_export_dir(root_dir: str) -> list[ManifestEntry]:
    """Walk a `readpst -c v -r` (VCard) output tree and stage every `.vcf` file."""
    entries: list[ManifestEntry] = []
    root = Path(root_dir)
    for path in sorted(root.rglob("*.vcf")):
        if not path.is_file() or path.stat().st_size == 0:
            continue
        try:
            parse_vcard_contact(path.read_bytes())
        except Exception:
            logger.warning("Failed to parse vcard %s, skipping", path, exc_info=True)
            continue
        folder_path = str(path.parent.relative_to(root))
        entries.append(
            ManifestEntry(
                id=str(uuid.uuid4()),
                doc_type="contact",
                staged_path=str(path),
                folder_path="" if folder_path == "." else folder_path,
            )
        )
    return entries


# --- subprocess-backed extraction (readpst) ---------------------------------------


def _run_readpst(args: list[str], timeout: int = 900) -> None:
    try:
        result = subprocess.run(
            ["readpst", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PSTExtractionError("readpst is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise PSTExtractionError(f"readpst timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise PSTExtractionError(
            f"readpst failed (exit {result.returncode}): {result.stderr.strip()}"
        )


def stage_contacts_via_readpst(pst_path: str, staging_dir: str) -> list[ManifestEntry]:
    out_dir = Path(staging_dir) / "contacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    _run_readpst(["-t", "c", "-c", "v", "-r", "-o", str(out_dir), pst_path])
    return manifest_from_contact_export_dir(str(out_dir))


def stage_mail_via_readpst(pst_path: str, staging_dir: str) -> list[ManifestEntry]:
    out_dir = Path(staging_dir) / "mail_fallback"
    out_dir.mkdir(parents=True, exist_ok=True)
    _run_readpst(["-t", "e", "-e", "-r", "-o", str(out_dir), pst_path])
    return manifest_from_mail_export_dir(str(out_dir))


# --- pypff-backed extraction (primary path) ----------------------------------------


def _find_record_entry(item, tag: int):
    try:
        for i in range(item.get_number_of_record_sets()):
            record_set = item.get_record_set(i)
            for j in range(record_set.get_number_of_entries()):
                entry = record_set.get_entry(j)
                if entry.get_entry_type() == tag:
                    return entry
    except Exception:
        return None
    return None


def _get_message_class(message) -> str:
    entry = _find_record_entry(message, _PR_MESSAGE_CLASS)
    if entry is None:
        return ""
    try:
        return (entry.get_data_as_string() or "").lower()
    except Exception:
        return ""


def _get_attachment_filename(attachment) -> str:
    for tag in (_PR_ATTACH_LONG_FILENAME, _PR_ATTACH_FILENAME):
        entry = _find_record_entry(attachment, tag)
        if entry is not None:
            try:
                name = entry.get_data_as_string()
                if name:
                    return name
            except Exception:
                continue
    return ""


def _get_attachment_mime_type(attachment) -> str:
    entry = _find_record_entry(attachment, _PR_ATTACH_MIME_TAG)
    if entry is not None:
        try:
            return entry.get_data_as_string() or ""
        except Exception:
            pass
    return ""


def _decode_body(value) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _headers_from_message(message) -> dict[str, str]:
    transport_headers = _decode_body(message.get_transport_headers()).strip()
    if transport_headers:
        try:
            parsed = BytesParser(policy=policy.default).parsebytes(
                transport_headers.encode("utf-8", errors="replace") + b"\n\n"
            )
            return {key: str(parsed[key]) for key in _PRESERVED_HEADERS if parsed[key]}
        except Exception:
            logger.warning(
                "Failed to parse transport_headers, synthesizing minimal headers", exc_info=True
            )

    headers: dict[str, str] = {}
    try:
        if message.get_subject():
            headers["Subject"] = message.get_subject()
    except Exception:
        pass
    try:
        if message.get_sender_name():
            headers["From"] = message.get_sender_name()
    except Exception:
        pass
    try:
        delivery_time = message.get_delivery_time()
        if delivery_time:
            headers["Date"] = format_datetime(delivery_time)
    except Exception:
        pass
    return headers


def _pypff_attachments(message) -> list[tuple[str, str, bytes]]:
    attachments = []
    try:
        count = message.get_number_of_attachments()
    except Exception:
        return attachments
    for i in range(count):
        try:
            attachment = message.get_attachment(i)
            data = attachment.read_buffer(attachment.get_size())
            filename = _get_attachment_filename(attachment) or f"attachment-{i}"
            mime_type = _get_attachment_mime_type(attachment) or "application/octet-stream"
            attachments.append((filename, mime_type, data))
        except Exception:
            logger.warning("Failed to read attachment %d, skipping it", i, exc_info=True)
    return attachments


def _stage_pypff_email(message, staging_dir: str) -> tuple[str, Path]:
    headers = _headers_from_message(message)
    plain = _decode_body(message.get_plain_text_body())
    html = _decode_body(message.get_html_body())
    attachments = _pypff_attachments(message)
    eml_bytes = build_eml_bytes(headers, plain, html, attachments)

    item_id = str(uuid.uuid4())
    path = Path(staging_dir) / f"{item_id}.eml"
    path.write_bytes(eml_bytes)
    return item_id, path


def _stage_pypff_calendar(message, staging_dir: str) -> tuple[str, Path]:
    item_id = str(uuid.uuid4())
    subject = ""
    try:
        subject = message.get_subject() or ""
    except Exception:
        pass
    path = Path(staging_dir) / f"{item_id}.calendar.json"
    path.write_text(json.dumps({"subject": subject}))
    return item_id, path


def _walk_pypff_folder(
    folder, staging_dir: str, folder_path: str, entries: list[ManifestEntry]
) -> None:
    try:
        name = folder.get_name() or ""
    except Exception:
        name = ""
    current_path = f"{folder_path}/{name}".strip("/") if name else folder_path

    for sub_folder in folder.sub_folders:
        _walk_pypff_folder(sub_folder, staging_dir, current_path, entries)

    for message in folder.sub_messages:
        try:
            message_class = _get_message_class(message)
            if "contact" in message_class:
                continue  # handled separately via readpst's VCard export
            if "appointment" in message_class or "schedule.meeting" in message_class:
                item_id, path = _stage_pypff_calendar(message, staging_dir)
                entries.append(
                    ManifestEntry(
                        id=item_id,
                        doc_type="calendar",
                        staged_path=str(path),
                        folder_path=current_path,
                    )
                )
            else:
                item_id, path = _stage_pypff_email(message, staging_dir)
                entries.append(
                    ManifestEntry(
                        id=item_id,
                        doc_type="email",
                        staged_path=str(path),
                        folder_path=current_path,
                    )
                )
        except Exception:
            logger.warning(
                "Failed to stage one message in folder %s, skipping it", current_path, exc_info=True
            )


def stage_mail_via_pypff(pst_path: str, staging_dir: str) -> list[ManifestEntry]:
    import pypff

    entries: list[ManifestEntry] = []
    pst = pypff.file()
    try:
        pst.open(pst_path)
        root = pst.get_root_folder()
        _walk_pypff_folder(root, staging_dir, "", entries)
    finally:
        try:
            pst.close()
        except Exception:
            pass

    if not entries:
        raise PSTExtractionError(f"pypff opened {pst_path} but found no messages")
    return entries


# --- orchestration -------------------------------------------------------------


def extract_pst(pst_path: str, staging_dir: str) -> ExtractionResult:
    Path(staging_dir).mkdir(parents=True, exist_ok=True)
    entries: list[ManifestEntry] = []
    fallback_used = False

    try:
        entries.extend(stage_mail_via_pypff(pst_path, staging_dir))
    except Exception:
        logger.warning(
            "pypff extraction failed for %s, falling back to readpst mail export",
            pst_path,
            exc_info=True,
        )
        fallback_used = True
        entries.extend(stage_mail_via_readpst(pst_path, staging_dir))

    try:
        entries.extend(stage_contacts_via_readpst(pst_path, staging_dir))
    except Exception:
        logger.warning(
            "readpst contact export failed for %s, continuing without contacts",
            pst_path,
            exc_info=True,
        )

    if not entries:
        raise PSTExtractionError(f"No items could be extracted from {pst_path}")

    return ExtractionResult(entries=entries, fallback_used=fallback_used)
