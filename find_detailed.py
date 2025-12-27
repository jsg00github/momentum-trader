#!/usr/bin/env python3
# Find and fix the extra brace and paren

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check line 682 - it should have a blank line between TradeJournal and App
# The issue might be missing blank lines

print("Checking lines 680-685:")
for i in range(679, 685):
    print(f"{i+1}: {lines[i].rstrip()}")

# Check the ending
print("\nChecking last 10 lines:")
for i in range(len(lines)-10, len(lines)):
    print(f"{i+1}: {lines[i].rstrip()}")

# Count total braces/parens
total_open_brace = sum(line.count('{') for line in lines)
total_close_brace = sum(line.count('}') for line in lines)
total_open_paren = sum(line.count('(') for line in lines)
total_close_paren = sum(line.count(')') for line in lines)

print(f"\nTotal: {{ {total_open_brace} vs }} {total_close_brace}")
print(f"Total: ( {total_open_paren} vs ) {total_close_paren}")

# Find where we have the issue - track from end
print("\nSearching for unclosed braces/parens from end...")
brace_bal = 0
paren_bal = 0

for i in range(len(lines)-1, -1, -1):
    line = lines[i]
    brace_bal += line.count('}') - line.count('{')
    paren_bal += line.count(')') - line.count('(')
    
    if brace_bal < 0:
        print(f"\nLine {i+1} has EXTRA opening brace:")
        print(f"  {line.strip()[:100]}")
        # Show context
        for j in range(max(0, i-2), min(len(lines), i+3)):
            marker = ">>>" if j == i else "   "
            print(f"{marker} {j+1}: {lines[j].rstrip()[:80]}")
        brace_bal = 0
        
    if paren_bal < 0:
        print(f"\nLine {i+1} has EXTRA opening paren:")
        print(f"  {line.strip()[:100]}")
        # Show context
        for j in range(max(0, i-2), min(len(lines), i+3)):
            marker = ">>>" if j == i else "   "
            print(f"{marker} {j+1}: {lines[j].rstrip()[:80]}")
        paren_bal = 0
