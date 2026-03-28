#!/usr/bin/env python3
"""Create a mapping of errors to problematic code lines"""

import re
import subprocess

# Run ty check
result = subprocess.run(
    ['.venv/bin/python', '-m', 'ty', 'check', 'plugin/'],
    capture_output=True,
    text=True,
    cwd='/home/keithcu/Desktop/Python/writeragent'
)

output = result.stdout

# Parse all errors with their context
error_blocks = re.findall(
    r'(error\[.*?\].*?--> plugin/[^:]*:\d+:\d+.*?(?:\n\|.*?)*?(?=\n\n|\Z))',
    output,
    re.DOTALL
)

print(f"Found {len(error_blocks)} error blocks")

# Write comprehensive error list
with open('errors_with_code.txt', 'w') as f:
    f.write(f"# Type Checking Errors with Problematic Code\n")
    f.write(f"# Total: {len(error_blocks)} errors\n\n")
    
    for i, block in enumerate(error_blocks, 1):
        # Extract file and line
        file_match = re.search(r'--> (plugin/[^:]*:\d+):', block)
        if file_match:
            location = file_match.group(1)
            f.write(f"## Error {i}: {location}\n")
            f.write(block + '\n\n')
            f.write("-" * 60 + "\n\n")

print(f"Written {len(error_blocks)} errors to errors_with_code.txt")