import sys

# Read the file
with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Keep lines 0-343 and 564+ (remove 344-563)
cleaned_lines = lines[:344] + lines[564:]

# Write the cleaned file
with open('backend/static/app.js', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print(f"Cleaned! Removed {564 - 344} lines of old Recharts code")
print(f"New file has {len(cleaned_lines)} lines")
