def check_balance(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    lines = content.split('\n')
    
    # Simple state machine to ignore strings and comments
    in_string = False
    string_char = None
    in_multiline_comment = False
    in_single_line_comment = False
    
    for line_idx, line in enumerate(lines):
        i = 0
        in_single_line_comment = False
        while i < len(line):
            char = line[i]
            
            if in_multiline_comment:
                if i + 1 < len(line) and line[i:i+2] == '*/':
                    in_multiline_comment = False
                    i += 2
                    continue
            elif in_single_line_comment:
                break
            elif in_string:
                if char == string_char and line[i-1] != '\\':
                    in_string = False
            else:
                if i + 1 < len(line) and line[i:i+2] == '/*':
                    in_multiline_comment = True
                    i += 2
                    continue
                if i + 1 < len(line) and line[i:i+2] == '//':
                    in_single_line_comment = True
                    break
                if char in ['"', "'", '`']:
                    in_string = True
                    string_char = char
                elif char in '({[':
                    stack.append((char, line_idx + 1, i + 1))
                elif char in ')}]':
                    if not stack:
                        print(f"Extra closing {char} at line {line_idx + 1}, col {i + 1}")
                        return False
                    last_char, last_line, last_col = stack.pop()
                    if last_char != pairs[char]:
                        print(f"Mismatched {char} at line {line_idx + 1}, col {i + 1}. Expected match for {last_char} from line {last_line}, col {last_col}")
                        return False
            i += 1
            
    if stack:
        for char, line, col in stack:
            print(f"Unclosed {char} from line {line}, col {col}")
        return False
        
    print("All brackets are balanced!")
    return True

if __name__ == "__main__":
    check_balance('static/app.js')
