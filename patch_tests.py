import re

with open("plugin/tests/test_csv_import_logic.py", "r") as f:
    content = f.read()

# Add a mock for self.bridge.parse_range_string which returns ((0, 0), (0, 0)) or similar.
# A1 is ((0,0), (0,0))
content = content.replace("self.bridge._index_to_column.return_value = \"A\"", "self.bridge._index_to_column.return_value = \"A\"\n        self.bridge.parse_range_string.return_value = ((0,0), (0,0))")

with open("plugin/tests/test_csv_import_logic.py", "w") as f:
    f.write(content)
