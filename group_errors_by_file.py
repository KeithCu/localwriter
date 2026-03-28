#!/usr/bin/env python3
"""Group unresolved-attribute errors by file for agent assignments"""

import subprocess
import re
from collections import defaultdict

# Run ty check and capture all unresolved-attribute errors
result = subprocess.run(
    ['.venv/bin/python', '-m', 'ty', 'check'],
    capture_output=True,
    text=True,
    cwd='/home/keithcu/Desktop/Python/writeragent'
)

# Parse all unresolved-attribute errors
error_pattern = r'error\[unresolved-attribute\]:.*?--> (plugin/[^:]*:\d+):'
errors_by_file = defaultdict(list)

for match in re.finditer(error_pattern, result.stdout, re.DOTALL):
    location = match.group(1)
    file_path = location.rsplit(':', 1)[0]  # Remove line number
    errors_by_file[file_path].append(location)

print(f"Found {len(errors_by_file)} files with unresolved-attribute errors")
print(f"Total errors: {sum(len(errors) for errors in errors_by_file.values())}")

# Group files for agents (10 files per agent)
files_list = sorted(errors_by_file.keys())
agent_groups = []

for i in range(0, len(files_list), 10):
    group = files_list[i:i+10]
    agent_groups.append(group)

# Write assignments
with open('unresolved_attribute_assignments.md', 'w') as f:
    f.write("# Unresolved Attribute Error Assignments\n\n")
    f.write(f"Total files: {len(files_list)}\n")
    f.write(f"Total errors: {sum(len(errors) for errors in errors_by_file.values())}\n\n")
    
    for i, group in enumerate(agent_groups, 1):
        f.write(f"## Agent {i}\n")
        f.write(f"Files assigned: {len(group)}\n")
        f.write(f"Errors to fix: {sum(len(errors_by_file[file]) for file in group)}\n\n")
        
        for file_path in group:
            error_count = len(errors_by_file[file_path])
            f.write(f"### {file_path}\n")
            f.write(f"**Errors**: {error_count}\n")
            f.write(f"**Locations**: {', '.join(errors_by_file[file_path])}\n\n")
        
        f.write("---\n\n")

print(f"Created assignments for {len(agent_groups)} agents")
print(f"Files per agent: {len(agent_groups[0]) if agent_groups else 0}")