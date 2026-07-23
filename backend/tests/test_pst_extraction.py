import pytest

from app.services.email_parsing import parse_eml_bytes
from app.services.pst_extraction import (
    PSTExtractionError,
    build_eml_bytes,
    extract_pst,
    manifest_from_contact_export_dir,
    manifest_from_mail_export_dir,
    parse_vcard_contact,
)

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
