import os

def replace_in_file(path, search, replace):
    with open(path, "r") as f:
        content = f.read()
    content = content.replace(search, replace)
    with open(path, "w") as f:
        f.write(content)

replace_in_file("docs/llm-hacks.md", "Instead of requiring a `delimiter` parameter, the tool `import_csv_from_string` now handles it automatically in `core/calc_manipulator.py`.", "Instead of requiring a `delimiter` parameter, the tool `write_formula_range` now handles it automatically in `plugin/modules/calc/manipulator.py` when CSV data is provided.")
replace_in_file("docs/llm-hacks.md", "CSV DATA: Use comma (,) for import_csv_from_string.", "CSV DATA: Use comma (,) for write_formula_range.")

replace_in_file("docs/calc-integration.md", "- Added `import_csv_from_string` tool: Parses CSV string (e.g., \"Name,Age\\nAlice,30\\nBob,25\") and bulk-inserts into sheet starting at a cell. No file I/O required—ideal for AI-generated or pasted data.", "- Enhanced `write_formula_range` tool: Parses CSV string (e.g., \"Name,Age\\nAlice,30\\nBob,25\") and bulk-inserts into sheet starting at a cell. No file I/O required—ideal for AI-generated or pasted data.")
replace_in_file("docs/calc-integration.md", "Use `write_formula_range` for bulk writes, `import_csv_from_string` for bulk data inserts.", "Use `write_formula_range` for bulk writes or bulk CSV data inserts.")

replace_in_file("README.md", "The `import_csv_from_string` tool allows the AI to generate and inject large datasets instantly.", "The `write_formula_range` tool allows the AI to generate and inject large CSV datasets instantly.")

replace_in_file("plugin/framework/constants.py", "CSV DATA: Use comma (,) for import_csv_from_string.", "CSV DATA: Use comma (,) for write_formula_range.")
replace_in_file("plugin/framework/constants.py", "- import_csv_from_string: Bulk insert CSV data into the sheet starting at a cell. Use for large datasets.", "")
replace_in_file("plugin/framework/constants.py", "- write_formula_range: Single string fills entire range; JSON array must match range size exactly (one value per cell). Use ranges for efficiency; avoid single-cell operations.", "- write_formula_range: Single string fills entire range; JSON array must match range size exactly (one value per cell). Alternatively, provide multiline CSV data to bulk insert starting at a cell. Use ranges for efficiency.")
replace_in_file("plugin/framework/constants.py", "set_cell_style after merging.", "set_cell_style after merging.\n") # Just to make sure formatting is good, might need manual check.
