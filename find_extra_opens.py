#!/usr/bin/env python3
# Find where the balances go wrong

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Track balances
brace_bal = 0
paren_bal = 0

# Lines where balance increases unexpectedly
brace_issues = []
paren_issues = []

for i, line in enumerate(lines, 1):
    prev_brace = brace_bal
    prev_paren = paren_bal
    
    brace_bal += line.count('{') - line.count('}')
    paren_bal += line.count('(') - line.count(')')
    
    # Track if balance increased by more than expected
    brace_change = brace_bal - prev_brace
    paren_change = paren_bal - prev_paren
    
    # If we end with positive balance, one of these lines has the extra
    if i == len(lines):
        print(f"Final brace balance: {brace_bal}")
        print(f"Final paren balance: {paren_bal}")

# Find the last lines that contribute to positive balance
print("\nSearching backwards from end...\n")

brace_bal = 0
paren_bal = 0

for i in range(len(lines)-1, -1, -1):
    line = lines[i]
    
    # Count in reverse (subtract opens, add closes)
    brace_bal += line.count('}') - line.count('{')
    paren_bal += line.count(')') - line.count('(')
    
    # When balance becomes negative going backwards, we found where extra opens are
    if brace_bal < 0:
        print(f"Line {i+1} has extra opening brace {{")
        print(f"  {line.strip()[:100]}")
        brace_bal = 0  # Reset to continue searching
        
    if paren_bal < 0:
        print(f"Line {i+1} has extra opening paren (")
        print(f"  {line.strip()[:100]}")
        paren_bal = 0  # Reset to continue searching
