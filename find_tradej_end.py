#!/usr/bin/env python3
# Find where TradeJournal function ends

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find TradeJournal start
tradej_start = None
for i, line in enumerate(lines):
    if 'function TradeJournal()' in line:
        tradej_start = i
        print(f"TradeJournal starts at line {i+1}")
        break

if tradej_start is None:
    print("TradeJournal not found!")
    exit(1)

# Find where it ends by tracking braces
depth = 0
for i in range(tradej_start, len(lines)):
    line = lines[i]
    depth += line.count('{') - line.count('}')
    
    if i > tradej_start and depth == 0:
        print(f"TradeJournal ends at line {i+1}")
        print(f"Line content: {line.strip()}")
        
        # Show next few lines
        print("\nNext 5 lines after TradeJournal:")
        for j in range(i+1, min(i+6, len(lines))):
            print(f"{j+1}: {lines[j].rstrip()}")
        break
else:
    print(f"TradeJournal never closes! Depth at end: {depth}")
