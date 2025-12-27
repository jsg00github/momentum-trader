#!/usr/bin/env python3
# Remove ALL Trade Journal code from app.js

with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove TradeJournal component definition
tradej_start = content.find('// --- Trade Journal Components ---')
app_start = content.find('function App()')

if tradej_start != -1 and app_start != -1:
    # Remove everything between tradej_start and app_start
    content = content[:tradej_start] + content[app_start:]
    print("✓ Removed TradeJournal component")

# 2. Remove view state from App
content = content.replace("const [view, setView] = useState('scanner'); // Scanner or Journal view\n", "")
content = content.replace("    const [view, setView] = useState('scanner'); // Scanner or Journal view\n", "")
print("✓ Removed view state")

# 3. Remove navigation tabs (looking for the tabs div)
# Find and remove the tabs section
import re

# Remove the navigation tabs div
tabs_pattern = r'\s*{/\* Navigation Tabs \*/}.*?</div>\s*</div>\s*<div className="flex items-center gap-4">'
content = re.sub(tabs_pattern, '\n                <div className="flex items-center gap-4">', content, flags=re.DOTALL)
print("✓ Removed navigation tabs")

# 4. Remove the view conditional rendering
# Replace: {view === 'journal' ? ( <TradeJournal /> ) : (
# With just the scanner content
view_check_pattern = r'\s*{view === [\'"]journal[\'"] \? \(\s*<TradeJournal />\s*\) : \(\s*'
content = re.sub(view_check_pattern, '\n                ', content, flags=re.DOTALL)
print("✓ Removed view conditional")

# 5. Remove closing of the conditional at the end
# Look for the extra )} before </div>
closing_pattern = r'\s*\)}\s*</div>\s*</div>\s*</div>\s*\);'
content = re.sub(closing_pattern, '\n            </div>\n        </div>\n    );', content, flags=re.DOTALL)
print("✓ Removed conditional closing")

with open('backend/static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

# Count braces
open_b = content.count('{')
close_b = content.count('}')
open_p = content.count('(')
close_p = content.count(')')

print(f"\n✓ Final braces: {{ {open_b} vs }} {close_b} - Diff: {open_b - close_b}")
print(f"✓ Final parens: ( {open_p} vs ) {close_p} - Diff: {open_p - close_p}")
print(f"✓ New file has {len(content.split(chr(10)))} lines")
