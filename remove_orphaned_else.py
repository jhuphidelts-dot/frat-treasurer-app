#!/usr/bin/env python3
"""
Remove orphaned '    else:' blocks (4-space indentation) that don't have matching if statements.
These are remnants from removing `if USE_DATABASE:` conditionals.
"""

def remove_orphaned_else_blocks(filename='app.py'):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    output = []
    i = 0
    removed_blocks = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for orphaned else at function level (exactly 4 spaces)
        if line == '    else:\n':
            # Look back to find if there's a matching if/try/for/while
            # at the same indentation level
            j = i - 1
            found_match = False
            
            # Skip back through the code
            while j >= 0:
                prev = lines[j].rstrip()
                
                # Skip empty lines
                if not prev:
                    j -= 1
                    continue
                
                # Count indentation
                indent = len(lines[j]) - len(lines[j].lstrip())
                
                # If we hit something at same indentation that could match
                if indent == 4:
                    stripped = lines[j].strip()
                    # Check if it's a valid block starter
                    if any(stripped.startswith(x) for x in ['if ', 'elif ', 'try:', 'for ', 'while ', 'with ']):
                        found_match = True
                        break
                    # If we hit a decorator, function def, or another statement, no match
                    elif stripped.startswith('def ') or stripped.startswith('@') or not prev.endswith(':'):
                        break
                
                # If we hit a function def at indent 0, definitely orphaned
                if indent == 0 and lines[j].strip().startswith('def '):
                    break
                
                j -= 1
            
            # If no match found, remove this else block
            if not found_match:
                print(f"Line {i+1}: Removing orphaned else block")
                removed_blocks += 1
                
                # Skip the else line
                i += 1
                
                # Skip all subsequent lines that are part of this else block (indent > 4)
                while i < len(lines):
                    next_line = lines[i]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    # If we hit a non-empty line at indent <= 4, we're done with this block
                    if next_line.strip() and next_indent <= 4:
                        break
                    
                    # Skip this line (part of the else block)
                    i += 1
                
                continue
        
        # Keep this line
        output.append(line)
        i += 1
    
    # Write result
    with open(filename, 'w') as f:
        f.writelines(output)
    
    print(f"\n✅ Removed {removed_blocks} orphaned else blocks")
    return removed_blocks

if __name__ == '__main__':
    remove_orphaned_else_blocks('app.py')
