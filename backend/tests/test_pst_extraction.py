import pytest

from app.services.email_parsing import parse_eml_bytes
from app.services.pst_extraction import (
    _MAX_RTF_DEENCAPSULATE_BYTES,
    _PR_ATTACH_CONTENT_ID,
    _PR_ATTACH_LONG_FILENAME,
    _PR_ATTACH_MIME_TAG,
    _PR_ATTACHMENT_HIDDEN,
    PSTExtractionError,
    _pypff_attachments,
    _rtf_deencapsulated_body,
    _stage_pypff_email,
    build_eml_bytes,
    extract_pst,
    manifest_from_contact_export_dir,
    manifest_from_mail_export_dir,
    parse_vcard_contact,
)

# Minimal MS-OXRTFCP encapsulated bodies -- what Outlook writes when a
# message's real plain-text/HTML content is wrapped in RTF rather than
# stored as a separate PR_BODY/PR_HTML property.
ENCAPSULATED_PLAIN_RTF = (
    rb"{\rtf1\fbidis\ansi\ansicpg1252\fromtext\deff0{\fonttbl{\f0\fswiss Arial;}}"
    rb"\viewkind4\uc1\pard\f0\fs20 Hello world, this is the real body.\par"
    rb"}"
)
ENCAPSULATED_HTML_RTF = (
    rb"{\rtf1\fbidis\ansi\ansicpg1252\fromhtml1\deff0{\fonttbl{\f0\fswiss Arial;}}"
    rb"{\*\htmltag64 <html>}{\*\htmltag72 <body>}"
    rb"{\*\htmltag1 <p>}Hello \b world\b0 !{\*\htmltag1 </p>}"
    rb"{\*\htmltag60 </body>}{\*\htmltag28 </html>}"
    rb"}"
)


class _FakeEntry:
    def __init__(self, tag, value, as_boolean=False):
        self._tag = tag
        self._value = value
        self._as_boolean = as_boolean

    def get_entry_type(self):
        return self._tag

    def get_data_as_string(self):
        return None if self._as_boolean else self._value

    def get_data_as_boolean(self):
        return self._value if self._as_boolean else None


class _FakeRecordSet:
    def __init__(self, entries):
        self._entries = entries

    def get_number_of_entries(self):
        return len(self._entries)

    def get_entry(self, j):
        return self._entries[j]


class _FakeAttachment:
    """Stands in for a pypff.attachment, exposing only what
    _pypff_attachments and its helpers touch."""

    def __init__(self, data, filename=None, mime_type=None, hidden=False, content_id=None):
        self._data = data
        entries = []
        if filename is not None:
            entries.append(_FakeEntry(_PR_ATTACH_LONG_FILENAME, filename))
        if mime_type is not None:
            entries.append(_FakeEntry(_PR_ATTACH_MIME_TAG, mime_type))
        if hidden:
            entries.append(_FakeEntry(_PR_ATTACHMENT_HIDDEN, True, as_boolean=True))
        if content_id is not None:
            entries.append(_FakeEntry(_PR_ATTACH_CONTENT_ID, content_id))
        self._record_set = _FakeRecordSet(entries)

    def get_size(self):
        return len(self._data)

    def read_buffer(self, _size):
        return self._data

    def get_number_of_record_sets(self):
        return 1

    def get_record_set(self, _i):
        return self._record_set


class _FakeMessage:
    """Stands in for a pypff.message, exposing only what _stage_pypff_email
    and its helpers touch."""

    def __init__(self, plain="", html="", rtf: bytes | None = None, attachments=None):
        self._plain = plain
        self._html = html
        self._rtf = rtf
        self._attachments = attachments or []

    def get_transport_headers(self):
        return ""

    def get_subject(self):
        return "Test subject"

    def get_sender_name(self):
        return "Alice"

    def get_delivery_time(self):
        return None

    def get_plain_text_body(self):
        return self._plain

    def get_html_body(self):
        return self._html

    def get_rtf_body(self):
        return self._rtf

    def get_number_of_attachments(self):
        return len(self._attachments)

    def get_attachment(self, i):
        return self._attachments[i]


SAMPLE_VCARD = """BEGIN:VCARD
VERSION:2.1
N:Smith;John;;;
FN:John Smith
EMAIL;TYPE=WORK:john.smith@example.com
EMAIL;TYPE=HOME:john.home@example.com
TEL;TYPE=WORK:+1-555-1234
ORG:Acme Corp
TITLE:Engineer
END:VCARD
"""


def test_build_eml_bytes_roundtrips_through_email_parsing():
    raw = build_eml_bytes(
        headers={
            "From": "alice@example.com",
            "To": "bob@example.com",
            "Subject": "Test subject",
            "Message-ID": "<m1@example.com>",
            "Content-Type": "should-be-ignored/not-preserved",
        },
        plain_text="plain body",
        html="<p>html body</p>",
        attachments=[("report.pdf", "application/pdf", b"%PDF-fake")],
    )
    parsed = parse_eml_bytes(raw)
    assert parsed.subject == "Test subject"
    assert parsed.sender == "alice@example.com"
    assert parsed.recipients_to == ["bob@example.com"]
    assert parsed.message_id == "<m1@example.com>"
    assert parsed.body_text.strip() == "plain body"
    assert "html body" in parsed.body_html
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "report.pdf"
    assert parsed.attachments[0].content == b"%PDF-fake"


def test_build_eml_bytes_plain_only_when_no_html():
    raw = build_eml_bytes(
        headers={"Subject": "Plain"}, plain_text="just text", html="", attachments=[]
    )
    parsed = parse_eml_bytes(raw)
    assert parsed.body_text.strip() == "just text"
    assert parsed.body_html == ""


def test_manifest_from_mail_export_dir_walks_nested_folders(tmp_path):
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    (inbox / "1.eml").write_bytes(b"From: a@x.com\nTo: b@x.com\nSubject: Hi\n\nbody\n")
    sent = tmp_path / "Sent Items"
    sent.mkdir()
    (sent / "2.eml").write_bytes(b"From: b@x.com\nTo: a@x.com\nSubject: Re: Hi\n\nreply\n")
    (tmp_path / "empty.eml").write_bytes(b"")
    (tmp_path / "garbage.txt").write_bytes(b"\x00\x01\x02 not an email at all, no headers")

    entries = manifest_from_mail_export_dir(str(tmp_path))
    folder_paths = {e.folder_path for e in entries}
    assert "Inbox" in folder_paths
    assert "Sent Items" in folder_paths
    assert len(entries) == 2
    assert all(e.doc_type == "email" for e in entries)


def test_manifest_from_mail_export_dir_skips_files_with_no_recognizable_content(tmp_path):
    (tmp_path / "junk.bin").write_bytes(b"\x00\x01\x02\x03")
    entries = manifest_from_mail_export_dir(str(tmp_path))
    assert entries == []


def test_parse_vcard_contact_extracts_fields():
    data = parse_vcard_contact(SAMPLE_VCARD)
    assert data["full_name"] == "John Smith"
    assert set(data["emails"]) == {"john.smith@example.com", "john.home@example.com"}
    assert data["phones"] == ["+1-555-1234"]
    assert data["company"] == "Acme Corp"
    assert data["title"] == "Engineer"


def test_manifest_from_contact_export_dir_walks_vcf_files(tmp_path):
    contacts_dir = tmp_path / "Contacts"
    contacts_dir.mkdir()
    (contacts_dir / "john.vcf").write_text(SAMPLE_VCARD)
    (contacts_dir / "broken.vcf").write_text("not a vcard at all")

    entries = manifest_from_contact_export_dir(str(tmp_path))
    assert len(entries) == 1
    assert entries[0].doc_type == "contact"
    assert entries[0].folder_path == "Contacts"


def test_extract_pst_raises_clear_error_on_non_pst_file(tmp_path):
    fake_pst = tmp_path / "not_a_real.pst"
    fake_pst.write_bytes(b"this is definitely not a valid PST file")
    staging = tmp_path / "staging"

    with pytest.raises(PSTExtractionError):
        extract_pst(str(fake_pst), str(staging))


def test_rtf_deencapsulated_body_recovers_plain_text():
    plain, html = _rtf_deencapsulated_body(_FakeMessage(rtf=ENCAPSULATED_PLAIN_RTF))
    assert "Hello world, this is the real body." in plain
    assert html == ""


def test_rtf_deencapsulated_body_recovers_html():
    plain, html = _rtf_deencapsulated_body(_FakeMessage(rtf=ENCAPSULATED_HTML_RTF))
    assert plain == ""
    assert "Hello" in html and "world" in html


def test_rtf_deencapsulated_body_returns_empty_when_no_rtf():
    plain, html = _rtf_deencapsulated_body(_FakeMessage(rtf=None))
    assert plain == ""
    assert html == ""


def test_rtf_deencapsulated_body_returns_empty_on_non_encapsulated_rtf():
    # Genuine free-form RTF (no \fromhtml1/\fromtext marker) can't be
    # de-encapsulated back to plain/HTML -- this should degrade gracefully
    # rather than raising.
    freeform_rtf = (
        rb"{\rtf1\ansi\deff0{\fonttbl{\f0\fswiss Arial;}}"
        rb"\viewkind4\uc1\pard\f0\fs20 Just a plain rtf doc.\par}"
    )
    plain, html = _rtf_deencapsulated_body(_FakeMessage(rtf=freeform_rtf))
    assert plain == ""
    assert html == ""


def test_rtf_deencapsulated_body_skips_oversized_bodies_without_parsing_them(monkeypatch):
    # A large RTF body is overwhelmingly a large embedded picture, not large
    # text (RTFDE's grammar-based parser measured ~13s for a 1MB body in a
    # real benchmark) -- extract_pst runs every message through this
    # synchronously in one thread, so a single such message would otherwise
    # stall the whole import. Confirms the cap skips DeEncapsulator entirely
    # rather than merely being fast for this particular oversized sample.
    import app.services.pst_extraction as pst_extraction_module

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("DeEncapsulator should not be invoked over the size cap")

    monkeypatch.setattr(pst_extraction_module, "DeEncapsulator", _fail_if_called)

    oversized_rtf = b"{\\rtf1\\fromtext " + (b"x" * (_MAX_RTF_DEENCAPSULATE_BYTES + 1)) + b"}"
    plain, html = _rtf_deencapsulated_body(_FakeMessage(rtf=oversized_rtf))
    assert plain == ""
    assert html == ""


def test_stage_pypff_email_falls_back_to_rtf_body_when_plain_and_html_are_empty(tmp_path):
    message = _FakeMessage(plain="", html="", rtf=ENCAPSULATED_PLAIN_RTF)
    _item_id, path = _stage_pypff_email(message, str(tmp_path))

    parsed = parse_eml_bytes(path.read_bytes())
    assert "Hello world, this is the real body." in parsed.body_text


def test_stage_pypff_email_prefers_native_plain_body_over_rtf(tmp_path):
    message = _FakeMessage(plain="Native plain body", html="", rtf=ENCAPSULATED_HTML_RTF)
    _item_id, path = _stage_pypff_email(message, str(tmp_path))

    parsed = parse_eml_bytes(path.read_bytes())
    assert parsed.body_text.strip() == "Native plain body"


def test_pypff_attachments_separates_hidden_inline_images_from_real_attachments():
    real = _FakeAttachment(b"%PDF-fake", filename="report.pdf", mime_type="application/pdf")
    inline = _FakeAttachment(
        b"PNGDATA", mime_type="image/png", hidden=True, content_id="sig123@test"
    )
    # A hidden attachment with no content ID can't be tied to any `cid:`
    # reference in the body -- dropped rather than shown as an attachment
    # or embedded nowhere.
    orphan_hidden = _FakeAttachment(b"ORPHAN", mime_type="image/png", hidden=True)

    attachments, inline_images = _pypff_attachments(
        _FakeMessage(attachments=[real, inline, orphan_hidden])
    )

    assert [a[0] for a in attachments] == ["report.pdf"]
    assert [(cid, mime) for cid, mime, _data in inline_images] == [("sig123@test", "image/png")]


def test_stage_pypff_email_embeds_inline_image_instead_of_listing_it_as_an_attachment(tmp_path):
    real = _FakeAttachment(b"%PDF-fake", filename="report.pdf", mime_type="application/pdf")
    signature_logo = _FakeAttachment(
        b"PNGDATA", mime_type="image/png", hidden=True, content_id="sig123@test"
    )
    message = _FakeMessage(
        plain="",
        html='<html><body>Regards<br><img src="cid:sig123@test"></body></html>',
        attachments=[real, signature_logo],
    )

    _item_id, path = _stage_pypff_email(message, str(tmp_path))
    parsed = parse_eml_bytes(path.read_bytes())

    assert [a.filename for a in parsed.attachments] == ["report.pdf"]
    assert "cid:sig123@test" not in parsed.body_html
    assert "data:image/png;base64," in parsed.body_html
