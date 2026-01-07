
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

# We'll inject a small debug div before the closing of the main div
debug_jsx = """
            {/* DEBUG PANEL */}
            <div className="mt-8 p-4 bg-slate-800/50 rounded border border-yellow-500/30 text-xs font-mono text-yellow-500">
                <h3 className="font-bold border-b border-yellow-500/30 mb-2">🔍 SYSTEM DIAGNOSTICS</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <p>Total Trades Loaded: {trades.length}</p>
                        <p>Active Groups: {Object.keys(activeGroups).length}</p>
                        <p>History Groups: {Object.keys(historyGroups).length}</p>
                        <p>Active Tab: {activeTab}</p>
                    </div>
                    <div>
                        <p>API Status: {loading ? 'Loading...' : 'Idle'}</p>
                        <p>First Trade: {trades.length > 0 ? JSON.stringify(trades[0].ticker) : 'None'}</p>
                        <p>Live Data Keys: {Object.keys(liveData).length}</p>
                    </div>
                </div>
            </div>
"""

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Look for the legend div to insert after it
legend_str = """<div className="flex items-center gap-1"><div className="w-3 h-3 bg-red-900/40 rounded"></div> Price {'<'} EMA</div>
            </div>"""

if legend_str in content:
    new_content = content.replace(legend_str, legend_str + "\n" + debug_jsx)
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(final_content := new_content)
    print("Success: Debug UI injected.")
else:
    print("Error: Could not find insert point (Legend div).")
    # Backup plan: insert before last closing div of component
    # This is risky if indentation varies but let's try strict replace first
