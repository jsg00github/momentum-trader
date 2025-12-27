with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "function Scanner" in line:
        print(f"Scanner starts at line {i+1}")
