#!/usr/bin/env python3
# Move TradeJournal definition before App component

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find where TradeJournal function starts (line 930)
# Find where it ends (look for closing brace at same indentation level)
# Move it before App function (around line 669)

tradej_start = None
app_start = None

for i, line in enumerate(lines):
    if 'function TradeJournal()' in line:
        tradej_start = i
        print(f"Found TradeJournal start at line {i+1}")
    if 'function App()' in line and app_start is None:
        app_start = i
        print(f"Found App start at line {i+1}")

if not tradej_start or not app_start:
    print("ERROR: Could not find both functions")
    exit(1)

# Find the end of TradeJournal (closing brace)
# TradeJournal starts at ~930, look for "}\n\n" pattern after it
tradej_end = None
indent_level = 0
for i in range(tradej_start, len(lines)):
    line = lines[i]
    # Count braces
    indent_level += line.count('{') - line.count('}')
    
    # When we're back to 0 and it's just a closing brace, that's the end
    if indent_level == 0 and i > tradej_start and line.strip() == '}':
        tradej_end = i
        print(f"Found TradeJournal end at line {i+1}")
        break

if not tradej_end:
    print("ERROR: Could not find TradeJournal end")
    exit(1)

# Extract TradeJournal code
tradej_code = lines[tradej_start:tradej_end+1]

# Remove TradeJournal from its current location
# Keep the comment line before it if it's "// --- Trade Journal Components ---"
comment_line = tradej_start - 2
if comment_line >= 0 and '// --- Trade Journal Components ---' in lines[comment_line]:
    tradej_code = [lines[comment_line], '\n'] + tradej_code
    del lines[comment_line:tradej_end+1]
    # Adjust app_start since we removed lines
    offset = tradej_end + 1 - comment_line
    if comment_line < app_start:
        app_start -= offset
else:
    del lines[tradej_start:tradej_end+1]
    offset = tradej_end + 1 - tradej_start
    if tradej_start < app_start:
        app_start -= offset

# Insert TradeJournal BEFORE App (with spacing)
insert_pos = app_start - 1  # Just before "function App()"
lines[insert_pos:insert_pos] = tradej_code + ['\n']

# Write back
with open('backend/static/app.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\n✓ Moved TradeJournal from line {tradej_start+1} to line {insert_pos+1}")
print("✓ TradeJournal now defined BEFORE App component")
