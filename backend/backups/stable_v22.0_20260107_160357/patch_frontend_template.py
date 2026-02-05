
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

# We want to add the template download button logic
# I'll inject a helper function `handleDownloadTemplate` and add the button to the header group

# 1. New Handler
new_handler = """
    const handleDownloadTemplate = () => {
        window.location.href = `${API_BASE}/trades/template`;
    };
"""

# 2. Updated Header Section with the new button (icon style or text)
# Existing:
# <button onClick={handleImportClick} ...>Import CSV</button>
# Target Replacement:
# <button onClick={handleDownloadTemplate} ... title="Download Template">⬇️</button>
# <button onClick={handleImportClick} ...>Import CSV</button>

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Insert Handler
anchor = "const handleImportClick = () => {"
if anchor in content:
    new_content = content.replace(anchor, new_handler + "\n    " + anchor)
else:
    print("Error: Anchor for handler not found")
    exit(1)

# Insert Button
# Finding the Import CSV button to prepend the Download button
button_anchor = """<button onClick={handleImportClick} className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-slate-600">
                        Import CSV
                    </button>"""

template_button = """<button onClick={handleDownloadTemplate} className="bg-slate-800 hover:bg-slate-700 text-slate-400 px-3 py-2 rounded-lg font-medium transition text-sm border border-slate-700" title="Download Template CSV">
                        ⬇️ CSV
                    </button>
                    """

if button_anchor in new_content:
    final_content = new_content.replace(button_anchor, template_button + button_anchor)
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Success: Frontend patched with Template Download button.")
else:
    print("Error: Button anchor not found. Please check file content.")
    # Fallback search if exact whitespace match fails?
    # Proceeding with exact match hope for now as it was just written
