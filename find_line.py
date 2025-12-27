# Find line 2236 specifically
with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Show context around line 2236
for i in range(2230, 2245):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
