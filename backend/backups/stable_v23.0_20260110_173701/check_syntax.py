
import ast
try:
    with open(r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\trade_journal.py", "r", encoding="utf-8") as f:
        ast.parse(f.read())
    print("Syntax OK")
except Exception as e:
    print(f"Syntax Error: {e}")
