import fitz

from app.services.pdf_processing import (
    RedactionRect,
    burn_in_redactions,
    merge_documents,
    stamp_bates,
)


def _make_pdf_with_text(text: str) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), text, fontsize=12)
    return doc


def test_burn_in_redactions_actually_removes_text_not_just_overlays_it():
    doc = _make_pdf_with_text("Employee SSN: 123-45-6789 is confidential")
    page = doc[0]
    # locate the exact rect around the SSN so we redact precisely that span
    hits = page.search_for("123-45-6789")
    assert hits, "test setup: expected to find the SSN text on the page"
    rect = hits[0]

    burn_in_redactions(
        doc,
        [
            RedactionRect(
                page_number=0,
                x=rect.x0 - 1,
                y=rect.y0 - 1,
                width=rect.width + 2,
                height=rect.height + 2,
            )
        ],
    )

    remaining_text = doc[0].get_text()
    assert "123-45-6789" not in remaining_text
    assert "Employee SSN" in remaining_text  # text outside the redaction box survives
    assert "confidential" in remaining_text

    # re-searching for the redacted string should also come up empty (not just
    # invisible under a black box — genuinely gone from the content stream)
    assert doc[0].search_for("123-45-6789") == []


def test_burn_in_redactions_only_affects_specified_page():
    doc = fitz.open()
    doc.new_page(width=612, height=792).insert_text((72, 72), "Page one secret")
    doc.new_page(width=612, height=792).insert_text((72, 72), "Page two secret")

    burn_in_redactions(doc, [RedactionRect(page_number=0, x=60, y=60, width=200, height=30)])

    assert "secret" not in doc[0].get_text()
    assert "secret" in doc[1].get_text()


def test_burn_in_redactions_ignores_out_of_range_page_numbers():
    doc = _make_pdf_with_text("some text")
    # should not raise even though page 5 doesn't exist
    burn_in_redactions(doc, [RedactionRect(page_number=5, x=0, y=0, width=10, height=10)])
    assert "some text" in doc[0].get_text()


def test_stamp_bates_sequential_labels_and_next_counter():
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.new_page(width=612, height=792)
    doc.new_page(width=612, height=792)

    first, last, next_start = stamp_bates(doc, "ABC", 1, 6)

    assert first == "ABC000001"
    assert last == "ABC000003"
    assert next_start == 4
    assert "ABC000001" in doc[0].get_text()
    assert "ABC000002" in doc[1].get_text()
    assert "ABC000003" in doc[2].get_text()


def test_stamp_bates_continues_from_a_later_start_number():
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    first, last, next_start = stamp_bates(doc, "XYZ", 100, 4)
    assert first == last == "XYZ0100"
    assert next_start == 101


def test_merge_documents_preserves_page_count_and_order():
    doc1 = _make_pdf_with_text("first document")
    doc2 = fitz.open()
    doc2.new_page(width=612, height=792).insert_text((72, 72), "second document page one")
    doc2.new_page(width=612, height=792).insert_text((72, 72), "second document page two")

    merged = merge_documents([doc1, doc2])

    assert merged.page_count == 3
    assert "first document" in merged[0].get_text()
    assert "second document page one" in merged[1].get_text()
    assert "second document page two" in merged[2].get_text()
