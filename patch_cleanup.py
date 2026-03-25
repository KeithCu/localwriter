import re

with open("plugin/modules/calc/manipulator.py", "r") as f:
    content = f.read()

# remove import_csv_from_string
match = re.search(r'    def import_csv_from_string\(self, csv_data: str, target_cell: str = "A1"\):(.*?)    # ── Chart ──', content, flags=re.DOTALL)
if match:
    content = content.replace(match.group(0), '    # ── Chart ──')
    with open("plugin/modules/calc/manipulator.py", "w") as f:
        f.write(content)

with open("plugin/modules/calc/cells.py", "r") as f:
    content = f.read()

# remove ImportCsv class
match = re.search(r'class ImportCsv\(ToolBase\):(.*?)class DeleteStructure\(ToolBase\):', content, flags=re.DOTALL)
if match:
    content = content.replace(match.group(0), 'class DeleteStructure(ToolBase):')
    with open("plugin/modules/calc/cells.py", "w") as f:
        f.write(content)
