with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove orphaned code from lines 1644-2179 (0-indexed: 1643-2178)
# Keep everything before line 1644 and after line 2179
cleaned_lines = lines[:1643] + lines[2179:]

with open('backend/static/app_v2.js', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print(f"Removed {2179 - 1643} orphaned lines")
print(f"New total lines: {len(cleaned_lines)}")
