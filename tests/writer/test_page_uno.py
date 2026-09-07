# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Live UNO: page_set_style_properties refuses header/footer off while content remains."""

from __future__ import annotations

from plugin.testing_runner import native_test
from plugin.tests.testing_utils import with_native_doc
from plugin.writer.page import (
    PageSetHeaderFooterText,
    PageSetStyleProperties,
)


def _tool_ctx(doc, ctx):
    from plugin.framework.tool import ToolContext

    services = None
    try:
        from plugin.main import get_services

        services = get_services()
    except Exception:
        services = None
    return ToolContext(doc, ctx, "writer", services, "test")


def _style_name(doc):
    styles = doc.getStyleFamilies().getByName("PageStyles")
    if styles.hasByName("Standard"):
        return "Standard"
    return styles.getElementNames()[0]


def _style(doc):
    name = _style_name(doc)
    return doc.getStyleFamilies().getByName("PageStyles").getByName(name), name


def _set_text(doc, ctx, region, content, **kwargs):
    return PageSetHeaderFooterText().execute(
        _tool_ctx(doc, ctx), style=_style_name(doc), region=region, content=content, **kwargs,
    )


def _set_props(doc, ctx, **kwargs):
    return PageSetStyleProperties().execute(
        _tool_ctx(doc, ctx), style=_style_name(doc), **kwargs,
    )


@native_test
@with_native_doc("writer")
def test_disable_header_refuses_while_text_remains(ctx, doc):
    applied = _set_text(doc, ctx, "header", "<p>Keep this header</p>")
    assert applied["status"] == "ok"
    style, _name = _style(doc)
    assert style.getPropertyValue("HeaderIsOn") is True
    before = style.getPropertyValue("HeaderText").getString()

    res = _set_props(doc, ctx, header_is_on=False)
    assert res["status"] == "error"
    assert "page_set_header_footer_text" in res["message"]
    assert style.getPropertyValue("HeaderIsOn") is True
    after = style.getPropertyValue("HeaderText").getString()
    assert "Keep this header" in after
    assert after == before


@native_test
@with_native_doc("writer")
def test_disable_header_ok_after_clear(ctx, doc):
    applied = _set_text(doc, ctx, "header", "<p>Temporary header</p>")
    assert applied["status"] == "ok"
    cleared = _set_text(doc, ctx, "header", "")
    assert cleared["status"] == "ok"

    res = _set_props(doc, ctx, header_is_on=False)
    assert res["status"] == "ok", res
    style, _name = _style(doc)
    assert style.getPropertyValue("HeaderIsOn") is False


@native_test
@with_native_doc("writer")
def test_disable_footer_refuses_while_text_remains(ctx, doc):
    applied = _set_text(doc, ctx, "footer", "<p>Keep this footer</p>")
    assert applied["status"] == "ok"
    style, _name = _style(doc)
    res = _set_props(doc, ctx, footer_is_on=False)
    assert res["status"] == "error"
    assert "footer" in res["message"]
    assert style.getPropertyValue("FooterIsOn") is True
    assert "Keep this footer" in style.getPropertyValue("FooterText").getString()


@native_test
@with_native_doc("writer")
def test_enable_header_allowed_with_content(ctx, doc):
    applied = _set_text(doc, ctx, "header", "<p>Already on</p>")
    assert applied["status"] == "ok"
    res = _set_props(doc, ctx, header_is_on=True)
    assert res["status"] == "ok"
    style, _name = _style(doc)
    assert style.getPropertyValue("HeaderIsOn") is True
    assert "Already on" in style.getPropertyValue("HeaderText").getString()


@native_test
@with_native_doc("writer")
def test_disable_empty_header_allowed(ctx, doc):
    style, _name = _style(doc)
    style.setPropertyValue("HeaderIsOn", True)
    header = style.getPropertyValue("HeaderText")
    header.setString("")
    res = _set_props(doc, ctx, header_is_on=False)
    assert res["status"] == "ok", res
    assert style.getPropertyValue("HeaderIsOn") is False


@native_test
@with_native_doc("writer")
def test_disable_header_refuses_while_table_remains(ctx, doc):
    style, _name = _style(doc)
    style.setPropertyValue("HeaderIsOn", True)
    header = style.getPropertyValue("HeaderText")
    header.setString("")
    tbl = doc.createInstance("com.sun.star.text.TextTable")
    tbl.initialize(1, 2)
    header.insertTextContent(header.createTextCursor(), tbl, False)
    tbl.getCellByName("A1").setString("Logo cell")
    tbl.getCellByName("B1").setString("Address cell")

    res = _set_props(doc, ctx, header_is_on=False)
    assert res["status"] == "error"
    assert style.getPropertyValue("HeaderIsOn") is True
    assert "Logo cell" in style.getPropertyValue("HeaderText").getString()


@native_test
@with_native_doc("writer")
def test_disable_header_refuses_first_page_letterhead(ctx, doc):
    style, _name = _style(doc)
    style.setPropertyValue("HeaderIsOn", True)
    style.setPropertyValue("FirstIsShared", False)
    shared = _set_text(doc, ctx, "header", "")
    first = _set_text(doc, ctx, "header_first", "<p>First-page letterhead</p>")
    assert shared["status"] == "ok" and first["status"] == "ok"

    res = _set_props(doc, ctx, header_is_on=False)
    assert res["status"] == "error"
    assert "header_first" in res["message"]
    assert style.getPropertyValue("HeaderIsOn") is True
    assert "First-page letterhead" in style.getPropertyValue("HeaderTextFirst").getString()
