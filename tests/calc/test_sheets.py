# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2024 John Balis
# Copyright (c) 2026 KeithCu (modifications and relicensing)
# Copyright (c) 2026 LibreCalc AI Assistant (Calc integration features, originally MIT)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_create_sheet_description_and_ok_mentions_no_cells_copied():
    from plugin.calc.sheets import CreateSheet

    desc = CreateSheet.description
    assert "no cells copied" in desc
    assert "write_formula_range" in desc
    assert "source" in desc
    # CRUD-only: stay specialized (delegation), do not promote to core.
    assert CreateSheet.tier == "specialized"

    ctx = SimpleNamespace(doc=MagicMock())
    sheets = MagicMock()
    sheets.getCount.return_value = 1
    with patch("plugin.calc.sheets.CalcBridge") as bridge_cls:
        bridge_cls.return_value.get_active_document.return_value.getSheets.return_value = sheets
        result = CreateSheet().execute(ctx, sheet="Sample")

    assert result["status"] == "ok"
    assert "no cells copied" in result["message"]
    sheets.insertNewByName.assert_called_once_with("Sample", 1)
