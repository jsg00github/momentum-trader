# Check for JSX/JavaScript syntax errors
import re

with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Look for common issues
issues = []

# Check for unmatched braces
open_braces = content.count('{')
close_braces = content.count('}')
if open_braces != close_braces:
    issues.append(f"Unmatched braces: {open_braces} open, {close_braces} close")

# Check for unmatched parentheses
open_parens = content.count('(')
close_parens = content.count(')')
if open_parens != close_parens:
    issues.append(f"Unmatched parentheses: {open_parens} open, {close_parens} close")

# Check for duplicate function definitions
functions = re.findall(r'^function (\w+)\(', content, re.MULTILINE)
duplicates = [f for f in functions if functions.count(f) > 1]
if duplicates:
    issues.append(f"Duplicate functions: {set(duplicates)}")

# Check line count
lines = content.split('\n')
print(f"Total lines: {len(lines)}")
print(f"Total chars: {len(content)}")

if issues:
    print("\n❌ ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("\n✅ No obvious syntax issues found")

# Find where DetailView is
for i, line in enumerate(lines):
    if 'function DetailView' in line:
        print(f"\nDetailView at line {i+1}")
        break
