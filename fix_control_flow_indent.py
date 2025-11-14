#!/usr/bin/env python3
"""
Fix indentation errors where content after control flow statements (if/else/try/except/for)
at 8-space level needs to be indented to 12 spaces.
"""

def fix_control_flow_indent(filename='app.py'):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    output = []
    i = 0
    fixed = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a control flow statement at 8 spaces
        if line.startswith('        ') and not line.startswith('         '):
            stripped = line.strip()
            if (stripped.endswith(':') and 
                any(stripped.startswith(kw) for kw in ['if ', 'else:', 'elif ', 'try:', 'except', 'for ', 'while ', 'with '])):
                
                # Add the control flow line
                output.append(line)
                i += 1
                
                # Indent all following lines at 8-space level until we hit another control flow or lower indent
                while i < len(lines):
                    next_line = lines[i]
                    
                    # Empty line - keep as is
                    if not next_line.strip():
                        output.append(next_line)
                        i += 1
                        continue
                    
                    # Line at 8 spaces (same as control flow)
                    if next_line.startswith('        ') and not next_line.startswith('         '):
                        next_stripped = next_line.strip()
                        
                        # Another control flow statement - stop indenting
                        if (next_stripped.endswith(':') and 
                            any(next_stripped.startswith(kw) for kw in ['if ', 'else:', 'elif ', 'except', 'for ', 'while ', 'with '])):
                            break
                        
                        # Regular line - needs indenting
                        output.append('    ' + next_line)
                        fixed += 1
                        i += 1
                    elif next_line.startswith('            '):
                        # Already properly indented (12+ spaces)
                        output.append(next_line)
                        i += 1
                    else:
                        # Different indentation level - stop
                        break
                
                continue
        
        output.append(line)
        i += 1
    
    with open(filename, 'w') as f:
        f.writelines(output)
    
    print(f"✅ Fixed {fixed} indentation issues")
    return fixed

if __name__ == '__main__':
    fix_control_flow_indent('app.py')
