import base64

from app.services.email_parsing import parse_eml_bytes

INLINE_IMAGE_BYTES = b"FAKEPNGBYTES"

WITH_INLINE_SIGNATURE_IMAGE = f"""From: alice@example.com
To: bob@example.com
Subject: Signed email
Date: Mon, 01 Jan 2024 12:00:00 -0500
Content-Type: multipart/related; boundary="REL"

--REL
Content-Type: text/html; charset="utf-8"

<p>Regards,<br><img src="cid:sig123@test"></p>
--REL
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <sig123@test>
Content-Disposition: inline

{base64.b64encode(INLINE_IMAGE_BYTES).decode()}
--REL--
""".encode()

SIMPLE_MULTIPART = b"""From: Alice Smith <alice@example.com>
To: Bob Jones <bob@example.com>, "Carol, X" <carol@example.com>
Cc: dave@example.com
Subject: =?utf-8?B?SGVsbG8g8J+YgA==?= World
Date: Mon, 01 Jan 2024 12:00:00 -0500
Message-ID: <abc123@example.com>
In-Reply-To: <parent1@example.com>
References: <root@example.com> <parent1@example.com>
Content-Type: multipart/mixed; boundary="BOUND"

--BOUND
Content-Type: multipart/alternative; boundary="ALT"

--ALT
Content-Type: text/plain; charset="utf-8"

Hello there, plain text body.
--ALT
Content-Type: text/html; charset="utf-8"

<p>Hello there, <b>html</b> body.</p>
--ALT--
--BOUND
Content-Type: application/pdf; name="doc.pdf"
Content-Disposition: attachment; filename="doc.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--BOUND--
"""

WITH_INLINE_IMAGE_MARKED_AS_ATTACHMENT = f"""From: alice@example.com
To: bob@example.com
Subject: Signed email
Date: Mon, 01 Jan 2024 12:00:00 -0500
Content-Type: multipart/related; boundary="REL"

--REL
Content-Type: text/html; charset="utf-8"

<p>Regards,<br><img src="cid:sig123@test"></p>
--REL
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <sig123@test>
Content-Disposition: attachment; filename="image001.png"

{base64.b64encode(INLINE_IMAGE_BYTES).decode()}
--REL--
""".encode()

WITH_UNREFERENCED_CONTENT_ID_IMAGE = f"""From: alice@example.com
To: bob@example.com
Subject: Stray image
Date: Mon, 01 Jan 2024 12:00:00 -0500
Content-Type: multipart/related; boundary="REL"

--REL
Content-Type: text/html; charset="utf-8"

<p>No image reference here.</p>
--REL
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <orphan123@test>
Content-Disposition: inline

{base64.b64encode(INLINE_IMAGE_BYTES).decode()}
--REL--
""".encode()

PLAIN_ONLY = b"""From: solo@example.com
To: recipient@example.com
Subject: No attachments here
Date: Tue, 02 Jan 2024 08:30:00 +0000

Just a plain body, no MIME parts.
"""


def test_parses_headers_and_addresses():
    parsed = parse_eml_bytes(SIMPLE_MULTIPART)
    assert parsed.subject == "Hello \U0001f600 World"
    assert parsed.sender == "alice@example.com"
    assert parsed.recipients_to == ["bob@example.com", "carol@example.com"]
    assert parsed.recipients_cc == ["dave@example.com"]
    assert parsed.message_id == "<abc123@example.com>"
    assert parsed.in_reply_to == "<parent1@example.com>"
    assert parsed.references == ["<root@example.com>", "<parent1@example.com>"]
    assert parsed.sent_at is not None
    assert parsed.sent_at.year == 2024


def test_parses_body_and_attachment():
    parsed = parse_eml_bytes(SIMPLE_MULTIPART)
    assert parsed.body_text == "Hello there, plain text body."
    assert "html</b> body" in parsed.body_html
    assert len(parsed.attachments) == 1
    attachment = parsed.attachments[0]
    assert attachment.filename == "doc.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.content.startswith(b"%PDF")


def test_parses_plain_non_multipart_email():
    parsed = parse_eml_bytes(PLAIN_ONLY)
    assert parsed.subject == "No attachments here"
    assert parsed.sender == "solo@example.com"
    assert parsed.recipients_to == ["recipient@example.com"]
    assert parsed.body_text.strip() == "Just a plain body, no MIME parts."
    assert parsed.body_html == ""
    assert parsed.attachments == []
    assert parsed.message_id == ""


def test_handles_missing_optional_headers_gracefully():
    raw = b"Subject: minimal\n\nbody only\n"
    parsed = parse_eml_bytes(raw)
    assert parsed.subject == "minimal"
    assert parsed.sender == ""
    assert parsed.recipients_to == []
    assert parsed.sent_at is None
    assert parsed.references == []


def test_inline_signature_image_is_embedded_in_body_not_listed_as_an_attachment():
    parsed = parse_eml_bytes(WITH_INLINE_SIGNATURE_IMAGE)
    assert parsed.attachments == []
    assert "cid:sig123@test" not in parsed.body_html
    expected_data_uri = f"data:image/png;base64,{base64.b64encode(INLINE_IMAGE_BYTES).decode()}"
    assert expected_data_uri in parsed.body_html


def test_cid_referenced_image_marked_attachment_disposition_is_still_treated_as_inline():
    # Regression test: real-world senders are inconsistent about
    # Content-Disposition -- long Outlook thread exports in particular mark
    # every cid-referenced image `attachment` rather than `inline`, relying
    # purely on the body's `cid:` reference for inline display (same as a
    # mail client does when rendering). Trusting Content-Disposition alone
    # previously turned every such image into its own spurious "document"
    # -- confirmed against a real 200-image Outlook thread export, where it
    # produced 197 phantom attachments for a single email.
    parsed = parse_eml_bytes(WITH_INLINE_IMAGE_MARKED_AS_ATTACHMENT)
    assert parsed.attachments == []
    assert "cid:sig123@test" not in parsed.body_html
    expected_data_uri = f"data:image/png;base64,{base64.b64encode(INLINE_IMAGE_BYTES).decode()}"
    assert expected_data_uri in parsed.body_html


def test_image_with_unreferenced_content_id_falls_back_to_a_normal_attachment():
    # A Content-ID alone doesn't make an image inline -- if the body never
    # actually references it via cid:, there's nowhere to embed it, so it
    # should show up as a normal attachment rather than silently vanishing.
    parsed = parse_eml_bytes(WITH_UNREFERENCED_CONTENT_ID_IMAGE)
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].content == INLINE_IMAGE_BYTES
    assert parsed.attachments[0].mime_type == "image/png"
