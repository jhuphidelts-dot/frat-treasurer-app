#!/usr/bin/env python3
"""
Fix remaining indentation issues in app.py after legacy code removal.
Specifically, dedent blocks that are indented 12 spaces (should be 8) within functions.
"""

import re

def fix_indentation(filename='app.py'):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    output = []
    fixes = 0
    
    for i, line in enumerate(lines, 1):
        # Check if line starts with exactly 12 spaces (wrongly indented function body content)
        if line.startswith('            ') and not line.startswith('             '):
            # Check if previous non-empty line suggests we're in a function
            # (has 8-space indentation or 4-space for function def)
            # Dedent by 4 spaces
            dedented = line[4:]
            output.append(dedented)
            if i < 100 or i > 3200:  # Only print first and last occurrences
                print(f"Line {i}: Dedented from 12 to 8 spaces")
            fixes += 1
        else:
            output.append(line)
    
    with open(filename, 'w') as f:
        f.writelines(output)
    
    print(f"\n✅ Fixed {fixes} indentation issues")
    return fixes

if __name__ == '__main__':
    fix_indentation('app.py')
