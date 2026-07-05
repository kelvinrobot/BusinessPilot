from app.services.document_service import DocumentSection, _render_docx, _render_pdf


def _sections() -> list[DocumentSection]:
    return [
        DocumentSection(
            heading="Business Overview",
            body="A longer paragraph of body text that spans the width of the page "
            "and includes an em dash—plus a few ‘curly quotes’ to exercise the "
            "latin-1 fallback path used for PDF rendering.",
        ),
        DocumentSection(heading="Market Opportunity", body="A second section back to back with the first."),
        DocumentSection(heading="Financial Snapshot", body="A third section to make sure multiple blocks in a row never starve each other of horizontal space."),
    ]


def test_render_pdf_with_multiple_sections_does_not_raise() -> None:
    data = _render_pdf("Executive Summary: Test Bakery", _sections())
    assert isinstance(data, bytes)
    assert len(data) > 500


def test_render_docx_with_multiple_sections_does_not_raise() -> None:
    data = _render_docx("Executive Summary: Test Bakery", _sections())
    assert isinstance(data, bytes)
    assert len(data) > 500
