#!/usr/bin/env python3
# Find the extra brace and paren

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Track brace balance line by line
brace_balance = 0
paren_balance = 0
bracket_balance = 0

print("Checking balance line by line...\n")

for i, line in enumerate(lines, 1):
    # Update balances for this line
    brace_balance += line.count('{') - line.count('}')
    paren_balance += line.count('(') - line.count(')')
    bracket_balance += line.count('[') - line.count(']')
    
    # Report if balance goes very negative (closing without opening)
    if brace_balance < -2:
        print(f"⚠️  Line {i}: Too many closing braces (balance: {brace_balance})")
        print(f"    {line[:100]}")
    
    if paren_balance < -2:
        print(f"⚠️  Line {i}: Too many closing parens (balance: {paren_balance})")
        print(f"    {line[:100]}")

print(f"\nFinal balances:")
print(f"Braces: {brace_balance} (should be 0)")
print(f"Parens: {paren_balance} (should be 0)")
print(f"Brackets: {bracket_balance} (should be 0)")

# Find lines with suspicious patterns
print("\n\nSuspicious patterns:")
for i, line in enumerate(lines, 1):
    # Lines with only closing braces/parens
    stripped = line.strip()
    if stripped in ['}', '});', ');', '};']:
        # Check if this might be extra
        if i < len(lines):
            next_line = lines[i].strip() if i < len(lines) else ""
            if next_line in ['}', '});', ');', '};']:
                print(f"Line {i}: {stripped}")
                print(f"Line {i+1}: {next_line}")
                print(f"  ^ Multiple closes in a row - might be duplicate\n")
