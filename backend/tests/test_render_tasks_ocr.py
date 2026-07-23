import io
import uuid

from PIL import Image, ImageDraw, ImageFont

from app.models.case import Case
from app.models.document import DocType, Document, OcrStatus
from app.models.user import User
from app.services import storage
from app.tasks.render_tasks import render_document
from tests.conftest import register_and_login

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _scanned_png_bytes(text: str) -> bytes:
    img = Image.new("RGB", (900, 250), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_FONT_PATH, 40)
    draw.text((30, 90), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _make_case(db_session) -> Case:
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.com", hashed_password="x", full_name="")
    db_session.add(user)
    await db_session.flush()
    case = Case(id=uuid.uuid4(), name="OCR case", description="", created_by_id=user.id)
    db_session.add(case)
    await db_session.commit()
    return case


async def test_scanned_image_attachment_gets_ocred(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_root", str(tmp_path))
    case = await _make_case(db_session)

    native_path = storage.save_native_file(
        case.id, uuid.uuid4(), "scan.png", _scanned_png_bytes("SETTLEMENT AMOUNT 445566")
    )
    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        doc_type=DocType.attachment,
        subject="scan.png",
        native_file_path=native_path,
        mime_type="image/png",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    await render_document(document.id, db_session)
    await db_session.refresh(document)

    assert document.render_error == ""
    assert document.ocr_status == OcrStatus.completed
    assert "SETTLEMENT" in document.ocr_text
    assert "445566" in document.ocr_text


async def test_office_attachment_with_real_text_is_not_ocred(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_root", str(tmp_path))
    case = await _make_case(db_session)

    native_path = storage.save_native_file(
        case.id, uuid.uuid4(), "note.txt", b"This document already has real extractable text."
    )
    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        doc_type=DocType.attachment,
        subject="note.txt",
        native_file_path=native_path,
        mime_type="text/plain",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    await render_document(document.id, db_session)
    await db_session.refresh(document)

    assert document.render_error == ""
    assert document.ocr_status == OcrStatus.not_applicable
    assert document.ocr_text == ""


async def test_email_documents_are_never_ocred(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_root", str(tmp_path))
    case = await _make_case(db_session)

    document = Document(
        id=uuid.uuid4(),
        case_id=case.id,
        doc_type=DocType.email,
        subject="Hello",
        sender="a@x.com",
        body_text="hi",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    await render_document(document.id, db_session)
    await db_session.refresh(document)

    assert document.ocr_status == OcrStatus.not_applicable
    assert document.ocr_text == ""


async def test_ocred_text_becomes_searchable_via_the_documents_endpoint(
    client, db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(storage.settings, "storage_root", str(tmp_path))
    await register_and_login(client, "admin@example.com")
    case_resp = await client.post("/api/cases", json={"name": "OCR search case"})
    case_id = case_resp.json()["id"]

    native_path = storage.save_native_file(
        uuid.UUID(case_id),
        uuid.uuid4(),
        "scan.png",
        _scanned_png_bytes("EXHIBIT ZORBATRON 778899"),
    )
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.attachment,
        subject="scan.png",
        native_file_path=native_path,
        mime_type="image/png",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    await render_document(document.id, db_session)

    # "zorbatron" is a made-up word that can only be found via the OCR'd text,
    # never via subject/sender/body_text -- proves the search_vector column
    # (rebuilt by Postgres from ocr_text) is actually wired into the query.
    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "zorbatron"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == str(document.id)


async def test_ocred_hyphenated_substring_matches_via_ilike_fallback(
    client, db_session, tmp_path, monkeypatch
):
    # Regression test: Postgres's tsvector parser tokenizes "CV-445566" into
    # 'cv' and '-445566' (hyphen glued to the numeric part), so a plain
    # websearch_to_tsquery("445566") does NOT match it -- only caught when
    # ocr_text is also covered by the ILIKE substring fallback.
    monkeypatch.setattr(storage.settings, "storage_root", str(tmp_path))
    await register_and_login(client, "admin2@example.com")
    case_resp = await client.post("/api/cases", json={"name": "OCR hyphen case"})
    case_id = case_resp.json()["id"]

    native_path = storage.save_native_file(
        uuid.UUID(case_id),
        uuid.uuid4(),
        "scan.png",
        _scanned_png_bytes("CASE NUMBER 2026-CV-445566"),
    )
    document = Document(
        id=uuid.uuid4(),
        case_id=uuid.UUID(case_id),
        doc_type=DocType.attachment,
        subject="scan.png",
        native_file_path=native_path,
        mime_type="image/png",
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(document)
    await db_session.commit()

    await render_document(document.id, db_session)

    resp = await client.get(f"/api/cases/{case_id}/documents", params={"q": "445566"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == str(document.id)
