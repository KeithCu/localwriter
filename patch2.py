import re

with open("plugin/modules/calc/manipulator.py", "r") as f:
    content = f.read()

# in write_formula_range we need to handle the new return type from _parse_formula_or_values_string
# If it's a 2D list (i.e. first element is a list), we flatten it, BUT we also calculate new `end` if
# total_cells == 1 and we have a 2D array. This handles the import_csv behavior where they specify a single cell.

diff = """<<<<<<< SEARCH
            # Normalise string-as-array from AI callers.
            if isinstance(formula_or_values, str):
                parsed = _parse_formula_or_values_string(formula_or_values)
                if parsed is not None:
                    formula_or_values = parsed

            if isinstance(formula_or_values, (list, tuple)):
                if len(formula_or_values) != total_cells:
                    raise UnoObjectError(
                        f"Array has {len(formula_or_values)} values but range has "
                        f"total_cells cells. Use a single string to fill the whole "
                        "range, or an array with exactly that many values for "
                        "cell-by-cell control."
                    )
                values = formula_or_values
=======
            # Normalise string-as-array from AI callers.
            if isinstance(formula_or_values, str):
                parsed = _parse_formula_or_values_string(formula_or_values)
                if parsed is not None:
                    formula_or_values = parsed

            if isinstance(formula_or_values, (list, tuple)):
                # Detect 2D array (e.g. from multiline CSV or JSON array of arrays)
                if len(formula_or_values) > 0 and isinstance(formula_or_values[0], (list, tuple)):
                    rows = len(formula_or_values)
                    cols = max(len(r) for r in formula_or_values)

                    # If target range is a single cell, expand it to fit the 2D array
                    if total_cells == 1:
                        end = (start[0] + cols - 1, start[1] + rows - 1)
                        num_rows = end[1] - start[1] + 1
                        num_cols = end[0] - start[0] + 1
                        total_cells = num_rows * num_cols

                        # Pad the 2D array to ensure it matches the full rectangular dimensions
                        padded_values = []
                        for r in formula_or_values:
                            row_vals = list(r)
                            row_vals.extend([""] * (cols - len(row_vals)))
                            padded_values.extend(row_vals)
                        formula_or_values = padded_values
                    else:
                        # Otherwise flatten it to compare with total_cells
                        flat_vals = []
                        for r in formula_or_values:
                            flat_vals.extend(r)
                        formula_or_values = flat_vals

                if len(formula_or_values) != total_cells:
                    raise UnoObjectError(
                        f"Array has {len(formula_or_values)} values but range has "
                        f"{total_cells} cells. Use a single string to fill the whole "
                        "range, or an array with exactly that many values for "
                        "cell-by-cell control."
                    )
                values = formula_or_values
>>>>>>> REPLACE"""
# wait, I'll just use replace_with_git_merge_diff directly
