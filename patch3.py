import re

with open("plugin/modules/calc/manipulator.py", "r") as f:
    content = f.read()

diff = """<<<<<<< SEARCH
                    # Pad rows to ensure uniform width, and flatten into 1D
                    flat_vals = []
                    for r in formula_or_values:
                        row_vals = list(r)
                        row_vals.extend([""] * (num_cols - len(row_vals)))
                        flat_vals.extend(row_vals)
                    formula_or_values = flat_vals
=======
                    # Pad rows to ensure uniform width, and flatten into 1D
                    flat_vals = []
                    for r in formula_or_values:
                        row_vals = list(r)
                        if num_cols > len(row_vals):
                            row_vals.extend([""] * (num_cols - len(row_vals)))
                        flat_vals.extend(row_vals[:num_cols])
                    formula_or_values = flat_vals
>>>>>>> REPLACE"""
# replace_with_git_merge_diff
