import re

# Read the file
with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and fix the problematic area around line 790-800
# The issue is that we need to properly wrap the scanner content in a conditional

# Find the line with "// Content" comment  
content_marker = "            {/* Content */}"
content_index = content.find(content_marker)

if content_index != -1:
    print("Found content marker")
    # Find the opening div after the marker
    after_marker = content[content_index:]
    
    # We need to inject the view conditional rendering properly
    # Replace the structure to add view === 'journal' check
    
    old_pattern = r"(            {/\* Content \*/}\r?\n            <div className=\"flex-1 overflow-auto p-6 container mx-auto max-w-7xl\">)"
    
    new_structure = """            {/* Content */}
            <div className="flex-1 overflow-auto">
                {view === 'journal' ? (
                    <TradeJournal />
                ) : (
                    <div className="p-6 container mx-auto max-w-7xl">"""
    
    content = re.sub(old_pattern, new_structure, content, count=1)
    
    # Find the closing of Modal and add the closing for the scanner view
    modal_close_pattern = r"(                {/\* Modal \*/}\r?\n                {selectedTicker && \(\r?\n                    <DetailView ticker={selectedTicker} onClose={\(\) => setSelectedTicker\(null\)} />\r?\n                \)}\r?\n                </>\r?\n                \)}\r?\n            </div>)"
    
    new_closing = """                {/* Modal */}
                {selectedTicker && (
                    <DetailView ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />
                )}
                    </div>
                )}
            </div>"""
    
    content = re.sub(modal_close_pattern, new_closing, content, count=1)
    
    print("Regex replacements done")
    
    # Write back
    with open('backend/static/app.js', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("File updated successfully!")
else:
    print("Content marker not found!")
