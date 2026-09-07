"""Unit tests for header/footer FODT extract helpers (no LibreOffice)."""

from plugin.writer.html_export import (
    FODT_REGION_TAGS,
    extract_fodt_tag,
    fodt_master_page_inner,
    fodt_region_inner,
)


_FODT = """<?xml version="1.0"?>
<office:document>
 <office:master-styles>
  <style:master-page style:name="Landscape" style:page-layout-name="pm0">
   <style:header><text:p>Wrong style</text:p></style:header>
  </style:master-page>
  <style:master-page style:name="Standard" style:page-layout-name="pm1">
   <style:header>
    <text:p>Acme LLP <text:page-number/></text:p>
   </style:header>
   <style:footer>
    <table:table><table:table-row><table:table-cell><text:p>Left</text:p></table:table-cell></table:table-row></table:table>
   </style:footer>
   <style:header-first>
    <text:p>First page letterhead</text:p>
   </style:header-first>
  </style:master-page>
 </office:master-styles>
 <office:automatic-styles>
  <style:page-layout style:name="pm1">
   <style:header-style>
    <style:header-footer-properties fo:min-height="1in"/>
   </style:header-style>
  </style:page-layout>
 </office:automatic-styles>
</office:document>
"""


def test_extract_fodt_tag_skips_header_style_and_first():
    """style:header must not match style:header-style or style:header-first."""
    inner = extract_fodt_tag(_FODT, "style:header")
    assert inner is not None
    assert "Acme LLP" in inner or "Wrong style" in inner
    assert "header-footer-properties" not in inner
    first = extract_fodt_tag(_FODT, "style:header-first")
    assert first is not None
    assert "First page letterhead" in first


def test_extract_fodt_tag_self_closing_is_empty():
    assert extract_fodt_tag('<style:header/>', "style:header") == ""
    assert extract_fodt_tag('<style:footer />', "style:footer") == ""


def test_extract_fodt_tag_missing_is_none():
    assert extract_fodt_tag("<office:document/>", "style:header") is None


def test_fodt_master_page_picks_named_style():
    inner = fodt_master_page_inner(_FODT, "Standard")
    assert inner is not None
    assert "Acme LLP" in inner
    assert "Wrong style" not in inner


def test_fodt_region_inner_shared_and_first():
    header = fodt_region_inner(_FODT, "Standard", "header")
    assert header is not None
    assert "Acme LLP" in header
    first = fodt_region_inner(_FODT, "Standard", "header_first")
    assert first is not None
    assert "First page letterhead" in first
    footer = fodt_region_inner(_FODT, "Standard", "footer")
    assert footer is not None
    assert "Left" in footer


def test_fodt_region_inner_falls_back_when_variant_missing():
    """Shared-only FODT has no header-left; read the shared header instead of empty."""
    left = fodt_region_inner(_FODT, "Standard", "header_left")
    assert left is not None
    assert "Acme LLP" in left


def test_fodt_region_tags_cover_page_regions():
    assert set(FODT_REGION_TAGS) == {
        "header", "footer", "header_first", "footer_first", "header_left", "footer_left",
    }
