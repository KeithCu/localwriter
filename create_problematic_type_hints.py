#!/usr/bin/env python3
"""Extract problematic type hints that cause ty errors"""

import re

# Read all type errors
with open('all_type_errors.txt', 'r') as f:
    errors = f.readlines()

# Extract file:line patterns from errors
problematic_locations = set()
for error in errors:
    # Match patterns like "plugin/file.py:123:"
    match = re.search(r'(plugin/[^:]+:\d+):', error)
    if match:
        problematic_locations.add(match.group(1))

# Now find the actual type hints at those locations
problematic_hints = []
for location in sorted(problematic_locations):
    file_path, line_num = location.rsplit(':', 1)
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            line_num_int = int(line_num) - 1
            if line_num_int < len(lines):
                line_content = lines[line_num_int].strip()
                # Check if this line has type annotations
                if (re.search(r':\s*(List\[|Dict\[|Optional\[|Union\[|Any|Tuple\[|Set\[|Callable\[|->)', line_content) or 
                    re.search(r'from typing import|import typing', line_content)):
                    problematic_hints.append(f"{location}: {line_content}")
    except FileNotFoundError:
        continue

# Write to file
with open('problematic_type_hints.txt', 'w') as f:
    for hint in problematic_hints:
        f.write(hint + '\n')

print(f"Found {len(problematic_hints)} problematic type hints")