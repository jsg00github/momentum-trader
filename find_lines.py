with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "function App" in line:
        print(f"App at line {i+1}")
    if "function MarketDashboard" in line:
        print(f"MarketDashboard at line {i+1}")
    if "root.render" in line:
        print(f"root.render at line {i+1}")
