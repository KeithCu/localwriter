### Reading / Summarizing
- **read_cell_range** – Read values from one or more cell ranges.  
- **get_sheet_summary** – Get a comprehensive summary of a sheet (size, headers, used area, charts, merges, annotations, shapes).  

### Writing / Editing
- **write_formula_range** – Write formulas or values to ranges (JSON array or string), bulk‑insert CSV data, or clear contents by passing empty data.  
- **delete_structure** – Delete rows or columns.  

### Formatting / Layout
- **set_cell_style** – Apply formatting (bold, colors, alignment, borders, number format, etc.) to ranges.  
- **merge_cells** – Merge specified cell ranges (optionally centered).  
- **sort_range** – Sort a range by a column, with optional header row.  

### Sheet Management
- **list_sheets** – List all sheet names in the workbook.  
- **switch_sheet** – Switch the active sheet.  
- **create_sheet** – Create a new sheet.  

### Charts
- **create_chart** – Create a chart from a data range (bar, column, line, pie, scatter).  
- **list_charts** – List all charts on the active sheet.  
- **get_chart_info** – Get detailed info about a specific chart.  
- **edit_chart** – Edit chart title, subtitle, or legend visibility.  
- **delete_chart** – Delete a chart by name.  

### Comments
- **add_cell_comment** – Add a comment to a cell.  
- **list_cell_comments** – List all cell comments on a sheet.  
- **delete_cell_comment** – Delete a comment from a cell.  

### Conditional Formatting
- **add_conditional_format** – Add a conditional formatting rule to a range.  
- **list_conditional_formats** – List conditional formatting rules on a range.  
- **remove_conditional_formats** – Remove a specific rule by index, or clear all rules if omitted.  

### Search & Options
- **search_in_spreadsheet** – Search for text/values and return matching cells.  
- **replace_in_spreadsheet** – Find‑and‑replace text/values across the sheet(s).  

### Analysis & Utilities
- **detect_and_explain_errors** – Detect formula errors in ranges and provide explanations/fix suggestions.  
- **list_named_ranges** – List all named ranges in the workbook.  

### External / Misc
- **generate_image** – Generate or edit an image from a text prompt (insert into sheet).  
- **web_research** – Perform a web search for information.  

---

## Overlap & Duplication Analysis

*(Note: The consolidations below have mostly been successfully implemented in the most recent commits!)*

Some of the functions above overlapped significantly or had partial implementations that duplicated functionality. Consolidating them led to a simpler, "fatter" API surface.

### 1. Sheet Summarization
**Overlapping APIs:** `get_sheet_summary` vs `get_sheet_overview`
- **Overlap:** Both APIs inspect the sheet and provide metadata (used area, headers, etc.). `get_sheet_summary` focuses on structure, while `get_sheet_overview` adds charts, merged cells, and annotations.
- **Recommendation:** Merge these into a single **`get_sheet_summary`** (or `get_sheet_overview`) tool that accepts optional boolean flags (e.g., `include_charts`, `include_annotations`) to control verbosity, returning a comprehensive overview of the sheet context.

### 2. Writing and Importing Data
**Overlapping APIs:** `write_formula_range` vs `import_csv_from_string`
- **Overlap:** `write_formula_range` takes a JSON array (or single string) to write to ranges, while `import_csv_from_string` does exactly the same thing but parses CSV first.
- **Recommendation:** Enhance **`write_data_range`** to accept either a JSON array or a CSV string directly, inferring the type or using an explicit format argument. This eliminates `import_csv_from_string`.

### 3. Clearing Data
**Overlapping APIs:** `clear_range` vs `write_formula_range` (with empty data)
- **Overlap:** Writing an empty string or null into a range achieves the same as clearing its contents. However, `clear_range` might also clear formatting or borders depending on implementation.
- **Recommendation:** If `write_formula_range` is robust enough, it could accept an empty/null value to clear cells. Alternatively, `clear_range` is fine to keep if it acts as a structured delete (handling formats/comments uniquely).

### 4. Conditional Formatting Deletion
**Overlapping APIs:** `remove_conditional_format` vs `clear_conditional_formats`
- **Overlap:** `remove_conditional_format` removes a specific rule by index, whereas `clear_conditional_formats` wipes them all.
- **Recommendation:** Merge into a single **`remove_conditional_formats`** tool that takes an optional `index` parameter. If `index` is omitted, it clears all conditional formats in the range.

### 5. Cell Comments Deletion
**Overlapping APIs:** `delete_cell_comment` vs `clear_range`
- **Overlap:** Clearing a cell should ideally clear its comments (if implemented as a "clear all" action). 
- **Recommendation:** Ensure `clear_range` accepts a parameter to specify what to clear (e.g., `contents`, `formats`, `comments`). This makes `delete_cell_comment` partially redundant if we can just call `clear_range(range, clear_types=["comments"])`.

### 6. Search vs Replace
**Overlapping APIs:** `search_in_spreadsheet` vs `replace_in_spreadsheet`
- **Overlap:** `replace_in_spreadsheet` inherently requires searching first.  
- **Recommendation:** While often separated for safety, you could combine them into a single `find_and_modify_cells` tool where if the `replacement` parameter is omitted, it acts as a pure search. Though keeping them separate is often better for LLM reasoning (Search -> Confirm -> Replace).
