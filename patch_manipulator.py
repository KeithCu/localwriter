import re

with open("plugin/modules/calc/manipulator.py", "r") as f:
    content = f.read()

# We need to detect multiline CSV inside _parse_formula_or_values_string
# Or we can handle it directly in write_formula_range.
# Wait, if we return a 2D list from _parse_formula_or_values_string, we can use it.
# Currently, _parse_formula_or_values_string returns a flat list (1D).
# If it's a multiline CSV, returning a 2D list makes sense.
# Wait, the comment says:
# "If the AI sends formula_or_values as a JSON-encoded string... We normalise LibreOffice-style semicolon separators and return a flat list."

# What if formula_or_values is a list of lists (2D array)?
# In write_formula_range:
# if isinstance(formula_or_values, (list, tuple)):
#    if len(formula_or_values) != total_cells:
#       raise UnoObjectError(
#           f"Array has {len(formula_or_values)} values but range has "
#           f"{total_cells} cells. Use a single string to fill the whole "
#           "range, or an array with exactly that many values for "
#           "cell-by-cell control."
#       )
#    values = formula_or_values

# So `formula_or_values` is currently expected to be a 1D list (flattened).

# For multiline CSV, if we parse it into a 2D array, we should calculate the target range
# if the provided range is just a single cell (e.g., "A1").
