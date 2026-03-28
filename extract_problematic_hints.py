#!/usr/bin/env python3
"""Extract problematic type hints with full context"""

import re
import subprocess
import os

# Run ty check and capture full output with file locations
result = subprocess.run(
    ['.venv/bin/python', '-m', 'ty', 'check', 'plugin/'],
    capture_output=True,
    text=True,
    cwd='/home/keithcu/Desktop/Python/writeragent'
)

# ty outputs to stdout, not stderr
output = result.stdout

# Parse errors to find problematic lines
error_pattern = r'error\[.*?\].*?--> (plugin/[^:]*:\d+):'
problematic_lines = set(re.findall(error_pattern, output))

print(f"Found {len(problematic_lines)} lines with type errors")

# Also try to find lines that have type annotations
# Let's look for common patterns in the files mentioned in errors
file_pattern = r'--> (plugin/[^:]+):'
files_with_errors = set(re.findall(file_pattern, output))

print(f"Files with errors: {len(files_with_errors)}")

# Now let's find type annotations in these files
problematic_hints = []
for file_path in sorted(files_with_errors):
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            for line_num, line_content in enumerate(lines, 1):
                line_content = line_content.strip()
                # Check if this line has type annotations that might be problematic
                if (re.search(r':\s*(List\[|Dict\[|Optional\[|Union\[|Tuple\[|Set\[|Callable\[|->|: \w+\[)', line_content) or
                    re.search(r'from typing import|import typing|from types import', line_content) or
                    re.search(r'\w+:\s*(str|int|bool|list|dict|Any|Optional|Union)', line_content)):
                    problematic_hints.append(f"{file_path}:{line_num}: {line_content}")
    except FileNotFoundError:
        continue

# Write to file
with open('problematic_type_hints_detailed.txt', 'w') as f:
    f.write(f"# Found {len(problematic_hints)} type hints in files with errors\n")
    f.write(f"# Files with errors: {len(files_with_errors)}\n\n")
    
    # Group by file
    by_file = {}
    for hint in problematic_hints:
        file_path = hint.split(':', 2)[0]
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(hint)
    
    for file_path in sorted(by_file.keys()):
        f.write(f"\n## {file_path}\n")
        for hint in by_file[file_path]:
            f.write(hint + '\n')

print(f"Written {len(problematic_hints)} type hints to problematic_type_hints_detailed.txt")
print(f"Files with errors: {len(files_with_errors)}")