# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2026 KeithCu
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""UNO tests: first-page letterhead logos land in HeaderTextFirst / FooterTextFirst."""

from __future__ import annotations

import os

from com.sun.star.text.TextContentAnchorType import AS_CHARACTER

from plugin.testing_runner import native_test
from plugin.tests.testing_utils import with_native_doc
from plugin.writer.images.image_tools import insert_image_into_header_footer
from plugin.writer.page import _scan_region_content


def _logo_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for rel in ("extension/assets/logo_32.png", "assets/logo_32.png"):
        path = os.path.join(root, *rel.split("/"))
        if os.path.isfile(path):
            return path
    return os.path.join(root, "extension", "assets", "logo_32.png")


def _standard_style(doc):
    return doc.getStyleFamilies().getByName("PageStyles").getByName("Standard")


def _assert_graphic_in_first_not_shared(doc, style, first_prop, shared_prop, graphic):
    first = style.getPropertyValue(first_prop)
    shared = style.getPropertyValue(shared_prop)
    first_scan = _scan_region_content(doc, first)
    shared_scan = _scan_region_content(doc, shared)
    assert first_scan["images"], "expected graphic in %s, scan=%r" % (first_prop, first_scan)
    assert not shared_scan["images"], (
        "graphic leaked into shared %s: first=%r shared=%r" % (shared_prop, first_scan, shared_scan)
    )
    assert graphic.getPropertyValue("AnchorType") == AS_CHARACTER


@native_test
@with_native_doc("writer")
def test_insert_image_header_first_not_shared_header(ctx, doc):
    """FirstIsShared=False: header_first writes HeaderTextFirst, not HeaderText.

    Shared HeaderText never reaches a different-first-page letterhead, so a
    logo inserted with target=header would repeat on every page and miss page 1.
    """
    logo = _logo_path()
    assert os.path.isfile(logo), "fixture image missing: %s" % logo
    style = _standard_style(doc)
    style.setPropertyValue("HeaderIsOn", True)
    style.setPropertyValue("FirstIsShared", False)
    placed = insert_image_into_header_footer(
        doc, logo, "header_first", width_mm=20, height_mm=20, ctx=ctx,
    )
    assert placed["graphic"] is not None
    assert placed["region"] == "header_first"
    assert placed["auto_height"] is True
    assert style.getPropertyValue("HeaderIsDynamicHeight") is True
    _assert_graphic_in_first_not_shared(
        doc, style, "HeaderTextFirst", "HeaderText", placed["graphic"],
    )


@native_test
@with_native_doc("writer")
def test_insert_image_footer_first_not_shared_footer(ctx, doc):
    logo = _logo_path()
    assert os.path.isfile(logo), "fixture image missing: %s" % logo
    style = _standard_style(doc)
    style.setPropertyValue("FooterIsOn", True)
    style.setPropertyValue("FirstIsShared", False)
    placed = insert_image_into_header_footer(
        doc, logo, "footer_first", width_mm=20, height_mm=20, ctx=ctx,
    )
    assert placed["graphic"] is not None
    assert placed["region"] == "footer_first"
    assert style.getPropertyValue("FooterIsDynamicHeight") is True
    _assert_graphic_in_first_not_shared(
        doc, style, "FooterTextFirst", "FooterText", placed["graphic"],
    )
