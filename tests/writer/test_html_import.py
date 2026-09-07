"""Unit tests for header/footer HTML apply helpers (no LibreOffice)."""

from plugin.writer.html_import import XHTML_FIELD_TITLES, field_spans_to_sentinels


def test_field_spans_to_sentinels_page_number():
    html = '<p>Confidential <span title="page-number"/> end</p>'
    out = field_spans_to_sentinels(html)
    assert "WAFIELD_page-number_WAFIELD" in out
    assert '<span title="page-number"/>' not in out


def test_field_spans_to_sentinels_closed_span():
    html = '<p>X <span title="page-count"></span> Y</p>'
    out = field_spans_to_sentinels(html)
    assert "WAFIELD_page-count_WAFIELD" in out


def test_field_spans_to_sentinels_leaves_unknown_title():
    html = '<p><span title="not-a-field"/></p>'
    assert field_spans_to_sentinels(html) == html


def test_field_spans_to_sentinels_noop_without_title():
    html = "<p>plain</p>"
    assert field_spans_to_sentinels(html) == html
    assert field_spans_to_sentinels("") == ""
    assert field_spans_to_sentinels(None) is None


def test_xhtml_field_titles_match_body_export():
    """Body document_to_content emits title=\"page-number\"; apply must know that name."""
    assert XHTML_FIELD_TITLES["page-number"] == "PageNumber"
    assert XHTML_FIELD_TITLES["page-count"] == "PageCount"
