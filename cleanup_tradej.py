#!/usr/bin/env python3
# Clean up leftover TradeJournal code

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 681 (end of TradeJournal)
# Delete everything until we find "function App()"

tradej_end = None
app_start = None

for i, line in enumerate(lines):
    if i == 680:  # Line 681 in 1-indexed
        tradej_end = i
        print(f"TradeJournal ends at line {i+1}")
    if 'function App()' in line and app_start is None:
        app_start = i
        print(f"App starts at line {i+1}")

if tradej_end is None or app_start is None:
    print("Could not find boundaries!")
    exit(1)

print(f"\nDeleting lines {tradej_end+2} to {app_start}")
print(f"That's {app_start - tradej_end - 1} lines")

# Show what we're deleting
print("\nLines to delete:")
for i in range(tradej_end+1, app_start):
    print(f"{i+1}: {lines[i].strip()}")

# Delete the lines
del lines[tradej_end+1:app_start]

# Write back
with open('backend/static/app.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\n✓ Cleaned up file")
print(f"✓ New file has {len(lines)} lines")
