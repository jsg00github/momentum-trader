with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

found = False
for i, line in enumerate(lines):
    if "function Scanner" in line:
        print(f"Scanner found at line {i+1}")
        found = True
        break
        
if not found:
    print("Scanner function NOT found in app.js")
