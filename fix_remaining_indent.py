#!/usr/bin/env python3
"""
Fix remaining indentation issues - content after if/else/try/except/for that needs indenting.
"""

def fix_remaining_indentation(filename='app.py'):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    output = []
    i = 0
    fixes = 0
    
    while i < len(lines):
        line = lines[i]
        output.append(line)
        
        # Check if this line is a control flow statement at 8 spaces that needs indented content
        if line.startswith('        ') and not line.startswith('         '):
            stripped = line.strip()
            # Control flow statements that require indented blocks
            if (stripped.endswith(':') and 
                any(stripped.startswith(kw) for kw in ['if ', 'else:', 'elif ', 'try:', 'except', 'for ', 'while ', 'with ', 'finally:'])):
                
                # Look at next line
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # If next line starts with exactly 8 spaces (same level), it needs more indent
                    if next_line.startswith('        ') and not next_line.startswith('             ') and next_line.strip():
                        # Need to indent all subsequent lines at this level
                        j = i + 1
                        while j < len(lines):
                            check_line = lines[j]
                            # If line starts with 8 spaces (same as control statement)
                            if check_line.startswith('        ') and not check_line.startswith('             '):
                                stripped_check = check_line.strip()
                                # Skip if empty
                                if not stripped_check:
                                    output.append(check_line)
                                    j += 1
                                    continue
                                    
                                # Stop if we hit another control flow at same level
                                if (stripped_check.endswith(':') and 
                                    any(stripped_check.startswith(kw) for kw in ['if ', 'else:', 'elif ', 'except', 'for ', 'while ', 'with ', 'finally:'])):
                                    break
                                
                                # Stop if we hit a function def or route decorator
                                if (check_line.startswith('@') or 
                                    check_line.startswith('def ') or
                                    check_line.startswith('class ')):
                                    break
                                
                                # Indent this line
                                output.append('    ' + check_line)
                                fixes += 1
                                j += 1
                            elif check_line.strip() == '':
                                # Empty line, keep it
                                output.append(check_line)
                                j += 1
                            else:
                                # Different indentation level, stop
                                break
                        
                        # Skip the lines we just processed
                        i = j
                        continue
        
        i += 1
    
    with open(filename, 'w') as f:
        f.writelines(output)
    
    print(f"✅ Fixed {fixes} indentation issues")
    return fixes

if __name__ == '__main__':
    fix_remaining_indentation('app.py')
