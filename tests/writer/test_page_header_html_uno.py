# Live UNO: header/footer HTML get → set → get (and set → get) roundtrips.

import os

from plugin.testing_runner import native_test
from plugin.tests.testing_utils import TestingFactory, with_native_doc
from plugin.writer.page import (
    PageGetHeaderFooterText,
    PageSetHeaderFooterText,
    PageSetStyleProperties,
    _scan_region_content,
)


def _tool_ctx(doc, ctx):
    from plugin.main import get_services

    return TestingFactory.create_context(
        doc=doc, ctx=ctx, env="native", doc_type="writer", services=get_services(),
    )


def _style_name(doc):
    styles = doc.getStyleFamilies().getByName("PageStyles")
    return "Standard" if styles.hasByName("Standard") else styles.getElementNames()[0]


def _region_text(doc, region):
    from plugin.writer.page import _REGION_PROPS, resolve_page_style

    style, _name = resolve_page_style(doc, _style_name(doc))
    _is_on, text_prop = _REGION_PROPS[region]
    return style.getPropertyValue(text_prop)


def _logo_path():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for rel in ("extension/assets/logo_32.png", "assets/logo_32.png"):
        path = os.path.join(root, *rel.split("/"))
        if os.path.isfile(path):
            return path
    return os.path.join(root, "extension", "assets", "logo_32.png")


def _get_html(tctx, region, include_images=False):
    return PageGetHeaderFooterText().execute(
        tctx,
        style=_style_name(tctx.doc),
        region=region,
        format="html",
        include_images=include_images,
    )


def _set_html(tctx, region, content, auto_height=True):
    return PageSetHeaderFooterText().execute(
        tctx,
        style=_style_name(tctx.doc),
        region=region,
        content=content,
        auto_height=auto_height,
    )


def _insert_page_number(doc, text_obj):
    cur = text_obj.createTextCursor()
    cur.gotoEnd(False)
    field = doc.createInstance("com.sun.star.text.textfield.PageNumber")
    try:
        field.setPropertyValue("NumberingType", 4)
    except Exception:
        pass
    text_obj.insertTextContent(cur, field, False)
    return field


def _has_field(text_obj):
    scan_fields = []
    try:
        enum = text_obj.createEnumeration()
    except Exception:
        return False
    while enum.hasMoreElements() is True:
        el = enum.nextElement()
        try:
            if el.supportsService("com.sun.star.text.TextTable"):
                continue
        except Exception:
            pass
        try:
            portions = el.createEnumeration()
        except Exception:
            continue
        while portions.hasMoreElements() is True:
            portion = portions.nextElement()
            try:
                if portion.getPropertyValue("TextPortionType") == "TextField":
                    scan_fields.append(True)
            except Exception:
                continue
    return bool(scan_fields)


def _has_table(text_obj):
    try:
        enum = text_obj.createEnumeration()
    except Exception:
        return False
    while enum.hasMoreElements() is True:
        el = enum.nextElement()
        try:
            if el.supportsService("com.sun.star.text.TextTable"):
                return True
        except Exception:
            continue
    return False


@native_test
@with_native_doc("writer")
def test_plain_header_and_footer_html_roundtrip(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(tctx, style=style, header_is_on=True, footer_is_on=True)
    header = _region_text(doc, "header")
    footer = _region_text(doc, "footer")
    header.setString("Plain Header Line")
    footer.setString("Plain Footer Line")

    got_h = _get_html(tctx, "header")
    assert got_h["status"] == "ok", got_h
    assert "Plain Header Line" in got_h["content"]
    set_h = _set_html(tctx, "header", got_h["content"])
    assert set_h["status"] == "ok", set_h
    got_h2 = _get_html(tctx, "header")
    assert "Plain Header Line" in got_h2["content"]
    assert "Plain Header Line" in header.getString()

    set_f = _set_html(tctx, "footer", "<p>Applied Footer</p>")
    assert set_f["status"] == "ok", set_f
    got_f = _get_html(tctx, "footer")
    assert got_f["status"] == "ok", got_f
    assert "Applied Footer" in got_f["content"]
    assert "Applied Footer" in footer.getString()


@native_test
@with_native_doc("writer")
def test_header_page_number_field_survives_html_roundtrip(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(tctx, style=style, header_is_on=True)
    header = _region_text(doc, "header")
    header.setString("Acme LLP ")
    _insert_page_number(doc, header)
    assert _has_field(header), "setup: PageNumber field missing in header"

    got = _get_html(tctx, "header")
    assert got["status"] == "ok", got
    assert "Acme LLP" in got["content"]
    assert 'title="page-number"' in got["content"], (
        "body XHTML represents PageNumber as <span title=\"page-number\"/>; header get must match. "
        "got=%r" % got["content"][:400]
    )

    set_res = _set_html(tctx, "header", got["content"])
    assert set_res["status"] == "ok", set_res
    header2 = _region_text(doc, "header")
    assert "Acme LLP" in header2.getString()
    assert _has_field(header2), (
        "set dropped the page-number field (silent drop is forbidden). html=%r"
        % got["content"][:400]
    )
    got2 = _get_html(tctx, "header")
    assert 'title="page-number"' in got2["content"]


@native_test
@with_native_doc("writer")
def test_footer_page_number_field_set_then_get(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(tctx, style=style, footer_is_on=True)
    html = '<p>Confidential <span title="page-number"/> end</p>'
    set_res = _set_html(tctx, "footer", html)
    assert set_res["status"] == "ok", set_res
    footer = _region_text(doc, "footer")
    assert "Confidential" in footer.getString()
    assert "end" in footer.getString()
    assert _has_field(footer), "set of title=page-number span must recreate a field"
    got = _get_html(tctx, "footer")
    assert 'title="page-number"' in got["content"]
    assert "Confidential" in got["content"]


@native_test
@with_native_doc("writer")
def test_header_table_letterhead_roundtrip(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(tctx, style=style, header_is_on=True)
    table_html = "<table><tr><td>LogoCell</td><td>AddrCell</td></tr></table>"
    set_res = _set_html(tctx, "header", table_html)
    assert set_res["status"] == "ok", set_res
    header = _region_text(doc, "header")
    assert _has_table(header), "1x2 table did not land in header"
    assert "LogoCell" in header.getString()
    assert "AddrCell" in header.getString()

    got = _get_html(tctx, "header")
    assert got["status"] == "ok", got
    assert "<table" in got["content"]
    assert "LogoCell" in got["content"]
    assert "AddrCell" in got["content"]

    set2 = _set_html(tctx, "header", got["content"])
    assert set2["status"] == "ok", set2
    header2 = _region_text(doc, "header")
    assert _has_table(header2)
    assert "LogoCell" in header2.getString()
    got2 = _get_html(tctx, "header")
    assert "<table" in got2["content"]


@native_test
@with_native_doc("writer")
def test_header_as_character_logo_roundtrip(ctx, doc):
    from plugin.writer.images.image_tools import insert_image_into_header_footer

    logo = _logo_path()
    assert os.path.isfile(logo), "fixture image missing: %s" % logo
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(tctx, style=style, header_is_on=True)
    insert_image_into_header_footer(doc, logo, "header", width_mm=12, height_mm=12, ctx=ctx)
    header = _region_text(doc, "header")
    scan = _scan_region_content(doc, header)
    assert scan["images"], "setup: AS_CHARACTER logo not visible to region scan"

    got = _get_html(tctx, "header", include_images=True)
    assert got["status"] == "ok", got
    assert "<img" in got["content"], "html get dropped the logo: %r" % got["content"][:300]
    assert "data:image" in got["content"], (
        "include_images=true must keep the embedded logo. got=%r" % got["content"][:200]
    )

    set_res = _set_html(tctx, "header", got["content"])
    assert set_res["status"] == "ok", set_res
    header2 = _region_text(doc, "header")
    scan2 = _scan_region_content(doc, header2)
    assert scan2["images"], "set of logo HTML dropped the image (silent drop is forbidden)"
    got2 = _get_html(tctx, "header", include_images=True)
    assert "<img" in got2["content"]


@native_test
@with_native_doc("writer")
def test_first_page_header_html_roundtrip(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(
        tctx, style=style, header_is_on=True, first_is_shared=False)
    shared = _region_text(doc, "header")
    first = _region_text(doc, "header_first")
    shared.setString("Shared header")
    first.setString("First-page letterhead")

    got_first = _get_html(tctx, "header_first")
    got_shared = _get_html(tctx, "header")
    assert got_first["status"] == "ok", got_first
    assert got_shared["status"] == "ok", got_shared
    assert "First-page letterhead" in got_first["content"]
    assert "Shared header" in got_shared["content"]
    assert "First-page letterhead" not in got_shared["content"]
    assert "Shared header" not in got_first["content"]

    set_res = _set_html(tctx, "header_first", got_first["content"])
    assert set_res["status"] == "ok", set_res
    assert "First-page letterhead" in _region_text(doc, "header_first").getString()
    assert "Shared header" in _region_text(doc, "header").getString()
    got_first2 = _get_html(tctx, "header_first")
    assert "First-page letterhead" in got_first2["content"]


@native_test
@with_native_doc("writer")
def test_footer_first_html_roundtrip(ctx, doc):
    tctx = _tool_ctx(doc, ctx)
    style = _style_name(doc)
    PageSetStyleProperties().execute(
        tctx, style=style, footer_is_on=True, first_is_shared=False)
    _region_text(doc, "footer").setString("Shared footer")
    _region_text(doc, "footer_first").setString("First-page footer")

    got = _get_html(tctx, "footer_first")
    assert got["status"] == "ok", got
    assert "First-page footer" in got["content"]
    set_res = _set_html(tctx, "footer_first", "<p>First-page footer applied</p>")
    assert set_res["status"] == "ok", set_res
    assert "First-page footer applied" in _region_text(doc, "footer_first").getString()
    assert "Shared footer" in _region_text(doc, "footer").getString()
