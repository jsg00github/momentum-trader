#!/usr/bin/env python3
# Create a completely clean app.js with minimal TradeJournal

# Read the current file to get the working parts
with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where TradeJournal starts and ends
tradej_start = content.find('// --- Trade Journal Components ---')
tradej_end = content.find('function App()')

if tradej_start == -1 or tradej_end == -1:
    print("Could not find boundaries!")
    exit(1)

# Extract everything BEFORE TradeJournal
before_tradej = content[:tradej_start]

# Extract everything FROM App() onwards
from_app = content[tradej_end:]

# Create minimal TradeJournal
minimal_tradej = '''// --- Trade Journal Components ---

function TradeJournal() {
    console.log("🔥 TradeJournal rendering");
    return (
        <div className="p-6">
            <h1 className="text-3xl font-bold text-white">📊 Trade Journal</h1>
            <button className="bg-blue-600 px-4 py-2 rounded mt-4">
                + Add Trade
            </button>
            <p className="text-white mt-4">Trade Journal is loading...</p>
        </div>
    );
}

'''

# Combine
new_content = before_tradej + minimal_tradej + from_app

# Write
with open('backend/static/app.js', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✓ Created clean app.js")
print(f"✓ File has {len(new_content.split(chr(10)))} lines")

# Count braces
open_b = new_content.count('{')
close_b = new_content.count('}')
open_p = new_content.count('(')
close_p = new_content.count(')')

print(f"✓ Braces: {{ {open_b} vs }} {close_b} - Diff: {open_b - close_b}")
print(f"✓ Parens: ( {open_p} vs ) {close_p} - Diff: {open_p - close_p}")
