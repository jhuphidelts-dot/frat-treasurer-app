#!/usr/bin/env python3
"""
Remove orphaned else blocks that were left after removing if USE_DATABASE conditionals.
These are else blocks at indentation level 4 (4 spaces) that don't have matching if statements.
"""

import re

def fix_orphaned_else_blocks(filename):
    """Remove orphaned else blocks from the file"""
    
    with open(filename, 'r') as f:
        lines = f.lines()
    
    # Track lines to keep
    output_lines = []
    i = 0
    removed_count = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is an orphaned else at function level (4 spaces indent)
        if line == '    else:\n':
            # This is potentially orphaned
            # Look for the corresponding if/elif/try/except/for/while
            # by checking previous non-empty, non-comment lines
            
            # Find the previous significant code line
            j = i - 1
            while j >= 0:
                prev_line = lines[j]
                stripped = prev_line.strip()
                
                # Skip empty lines and comments
                if not stripped or stripped.startswith('#'):
                    j -= 1
                    continue
                
                # Check indentation
                indent = len(prev_line) - len(prev_line.lstrip())
                
                # If we find a line with same or less indentation that ends with :
                # it could be the matching block
                if indent <= 4 and prev_line.rstrip().endswith(':'):
                    # Check if it's an if/elif/try/except/for/while
                    if any(stripped.startswith(kw) for kw in ['if ', 'elif ', 'try:', 'except', 'for ', 'while ']):
                        # This else has a matching block, keep it
                        break
                
                # If we find a return/break/continue/pass at indent 8, keep looking
                if indent == 8:
                    j -= 1
                    continue
                
                # If we hit a function def or class def, this else is orphaned
                if indent == 0 or (indent == 4 and stripped.startswith('def ')):
                    # Orphaned! Remove this else block
                    print(f"Line {i+1}: Found orphaned else block")
                    
                    # Skip the else line
                    i += 1
                    removed_count += 1
                    
                    # Skip subsequent lines that are part of this else block (indent >= 8)
                    while i < len(lines):
                        next_line = lines[i]
                        next_indent = len(next_line) - len(next_line.lstrip())
                        
                        # Stop if we hit a line with indent <= 4 (back to function level)
                        if next_line.strip() and next_indent <= 4:
                            break
                        
                        # Skip lines in the else block
                        print(f"  Line {i+1}: Skipping else block content")
                        i += 1
                        removed_count += 1
                    
                    # Don't increment i again, we're already at the next line
                    continue
                
                break
            
            # If we didn't remove it above, keep it
            if i < len(lines) and lines[i] == line:
                output_lines.append(line)
                i += 1
        else:
            output_lines.append(line)
            i += 1
    
    # Write back
    with open(filename, 'w') as f:
        f.writelines(output_lines)
    
    print(f"\nRemoved {removed_count} lines total")
    return removed_count

if __name__ == '__main__':
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else 'app.py'
    fix_orphaned_else_blocks(filename)
