# Find all .toFixed() calls that might fail
import re

with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Look for .toFixed without null/undefined check
issues = []
for i, line in enumerate(lines):
    if '.toFixed(' in line:
        # Check if it's in DetailView area (around line 1811)
        if 1700 < i < 2500:
            # Check if there's no safety check
            if '?' not in line and 'if ' not in line:
                issues.append((i+1, line.strip()))

print("Potential unsafe .toFixed() calls in DetailView area:")
for line_num, content in issues[:15]:
    print(f"Line {line_num}: {content[:100]}")
