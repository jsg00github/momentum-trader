#!/usr/bin/env python3
# Check for syntax issues in app.js

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Count opening and closing braces, brackets, and parens
open_braces = content.count('{')
close_braces = content.count('}')
open_parens = content.count('(')
close_parens = content.count(')')
open_brackets = content.count('[')
close_brackets = content.count(']')

print(f"Braces: {{ {open_braces} vs }} {close_braces} - Diff: {open_braces - close_braces}")
print(f"Parens: ( {open_parens} vs ) {close_parens} - Diff: {open_parens - close_parens}")
print(f"Brackets: [ {open_brackets} vs ] {close_brackets} - Diff: {open_brackets - close_brackets}")

# Check if TradeJournal function exists
if 'function TradeJournal()' in content:
    print("\n✓ TradeJournal function found")
else:
    print("\n✗ TradeJournal function NOT found")

# Find where TradeJournal is called
if '<TradeJournal' in content:
    # Find the line number
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if '<TradeJournal' in line:
            print(f"✓ TradeJournal called at line {i}")
            # Show surrounding context
            start = max(0, i-3)
            end = min(len(lines), i+2)
            print("\nContext:")
            for j in range(start, end):
                marker = ">>> " if j == i-1 else "    "
                print(f"{marker}{j+1}: {lines[j][:80]}")
            break
else:
    print("\n✗ TradeJournal component NOT called")

# Check if function is defined before it's used
tradej_def_line = None
tradej_use_line = None

lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'function TradeJournal()' in line:
        tradej_def_line = i
    if '<TradeJournal' in line and tradej_use_line is None:
        tradej_use_line = i

print(f"\nTradeJournal defined at line: {tradej_def_line}")
print(f"TradeJournal used at line: {tradej_use_line}")

if tradej_def_line and tradej_use_line:
    if tradej_use_line < tradej_def_line:
        print("\n⚠️  WARNING: TradeJournal is used BEFORE it's defined!")
        print("   This will cause 'TradeJournal is not defined' error")
    else:
        print("\n✓ Order is correct (defined before used)")
