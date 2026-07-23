from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.parser import BytesParser


@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    content: bytes


@dataclass
class ParsedEmail:
    subject: str = ""
    sender: str = ""
    recipients_to: list[str] = field(default_factory=list)
    recipients_cc: list[str] = field(default_factory=list)
    recipients_bcc: list[str] = field(default_factory=list)
    sent_at: datetime | None = None
    message_id: str = ""
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)
    body_text: str = ""
    body_html: str = ""
    attachments: list[ParsedAttachment] = field(default_factory=list)


def _addr_list(msg, header: str) -> list[str]:
    field_value = msg[header]
    if not field_value:
        return []
    try:
        return [a.addr_spec for a in field_value.addresses if a.addr_spec]
    except (AttributeError, ValueError):
        return []


def parse_eml_bytes(raw: bytes) -> ParsedEmail:
    """Parse an RFC822 .eml byte string into structured fields.

    Uses the modern `email.policy.default` API so MIME-encoded headers
    (subject, display names, filenames) are decoded automatically.
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    sender = ""
    from_field = msg["from"]
    if from_field:
        try:
            addresses = from_field.addresses
            sender = addresses[0].addr_spec if addresses else str(from_field)
        except (AttributeError, ValueError, IndexError):
            sender = str(from_field)

    sent_at: datetime | None = None
    date_field = msg["date"]
    if date_field:
        try:
            sent_at = date_field.datetime
        except (AttributeError, ValueError, TypeError):
            sent_at = None

    references_raw = str(msg["references"] or "")
    references = references_raw.split()

    body_text = ""
    body_html = ""
    attachments: list[ParsedAttachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            content_type = part.get_content_type()
            filename = part.get_filename()
            if disposition == "attachment" or (disposition != "inline" and filename):
                payload = part.get_payload(decode=True) or b""
                attachments.append(
                    ParsedAttachment(
                        filename=filename or "attachment",
                        mime_type=content_type,
                        content=payload,
                    )
                )
            elif content_type == "text/plain" and not body_text:
                body_text = part.get_content()
            elif content_type == "text/html" and not body_html:
                body_html = part.get_content()
    else:
        if msg.get_content_type() == "text/html":
            body_html = msg.get_content()
        else:
            body_text = msg.get_content()

    return ParsedEmail(
        subject=str(msg["subject"] or ""),
        sender=sender,
        recipients_to=_addr_list(msg, "to"),
        recipients_cc=_addr_list(msg, "cc"),
        recipients_bcc=_addr_list(msg, "bcc"),
        sent_at=sent_at,
        message_id=str(msg["message-id"] or "").strip(),
        in_reply_to=str(msg["in-reply-to"] or "").strip(),
        references=references,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
    )
