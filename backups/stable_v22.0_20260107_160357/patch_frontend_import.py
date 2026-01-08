
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

# 1. Add file input usage and handlers
handlers_logic = """
    const fileInputRef = React.useRef(null);

    const handleImportClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        setLoading(true);
        try {
            const res = await axios.post(`${API_BASE}/trades/import`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            
            if (res.data.errors && res.data.errors.length > 0) {
                alert(`Imported with some errors:\n${res.data.errors.join("\\n")}`);
            } else {
                alert(res.data.message || "Import successful!");
            }
            fetchData(); // Refresh list
        } catch (e) {
            console.error(e);
            alert("Import failed: " + (e.response?.data?.error || e.message));
        } finally {
            setLoading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = ""; // Reset input
            }
        }
    };
"""

# 2. Add the button to the header
header_buttons_logic = """                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        Portfolio Tracker
                        <button onClick={fetchLivePrices} disabled={refreshing} className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded transition text-slate-400">
                            {refreshing ? '↻ Syncing...' : '↻ Refresh Prices'}
                        </button>
                    </h2>
                </div>
                <div className="flex gap-2">
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        onChange={handleFileChange} 
                        style={{ display: 'none' }} 
                        accept=".csv"
                    />
                    <button onClick={handleImportClick} className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-slate-600">
                        Import CSV
                    </button>
                    <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm">
                        {showForm ? 'Cancel' : '+ Log Trade'}
                    </button>
                </div>"""

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Insert handlers at the top of TradeJournal (after existing state defs)
# We can find `const handleDelete` as an anchor since it's defined before return
handler_anchor = "const handleDelete = async (id) => {"
handler_idx = content.find(handler_anchor)

if handler_idx != -1:
    new_content = content[:handler_idx] + handlers_logic + "\n\n    " + content[handler_idx:]
else:
    print("Error: Could not find handler anchor")
    exit(1)

# Replace the header section
# We'll target the whole div block to act as replacement
start_marker = "<div>\n                    <h2 className=\"text-2xl font-bold text-white tracking-tight flex items-center gap-2\">"
end_marker = "{showForm ? 'Cancel' : '+ Log Trade'}\n                </button>\n            </div>"

# Use looser search or specific unique chunks
chunk_start = """<div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">"""
chunk_end = """<button onClick={() => setShowForm(!showForm)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm">
                    {showForm ? 'Cancel' : '+ Log Trade'}
                </button>
            </div>"""

idx_start = new_content.find(chunk_start)
idx_end = new_content.find(chunk_end)

if idx_start != -1 and idx_end != -1:
    # We replace from start of headers div to end of "Log Trade" button div
    # The chunk_end is the END of the content to replace.
    # So we want to replace everything from idx_start to (idx_end + len(chunk_end))
    
    final_content = new_content[:idx_start] + header_buttons_logic + new_content[idx_end + len(chunk_end):]
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Success: Frontend patched with Import button.")
else:
    print("Error: Could not find header markers.")
    print(f"Start: {idx_start}, End: {idx_end}")

