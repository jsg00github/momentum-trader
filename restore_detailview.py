import re

# Read app.js to extract TradingViewChart, MetricCard and DetailView
with open('backend/static/app.js', 'r', encoding='utf-8') as f:
    app_content = f.read()

# Extract the components we need (lines 17-631)
# TradingViewChart (line 17-203), MetricCard (205-213), DetailView (215-631)
lines = app_content.split('\n')

# Get TradingViewChart component
trading_view_start = None
for i, line in enumerate(lines):
    if 'function TradingViewChart({' in line and trading_view_start is None:
        trading_view_start = i
        break

# Get MetricCard
metric_card_start = None
for i, line in enumerate(lines):
    if 'function MetricCard({' in line:
        metric_card_start = i
        break

# Get DetailView  
detail_view_start = None
for i, line in enumerate(lines):
    if 'function DetailView({' in line:
        detail_view_start = i
        break

# Find end of DetailView (next function or end)
detail_view_end = None
for i in range(detail_view_start + 1, len(lines)):
    if lines[i].startswith('function ') and 'DetailView' not in lines[i]:
        detail_view_end = i
        break

print(f"TradingViewChart: {trading_view_start}")
print(f"MetricCard: {metric_card_start}")
print(f"DetailView: {detail_view_start} to {detail_view_end}")

# Extract components
components_to_insert = '\n'.join(lines[trading_view_start:detail_view_end])

# Now read app_v2.js and find where to replace DetailView
with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    app_v2_content = f.read()

lines_v2 = app_v2_content.split('\n')

# Find DetailView in app_v2.js
detail_view_v2_start = None
for i, line in enumerate(lines_v2):
    if 'function DetailView({' in line or '// Detail View' in line:
        detail_view_v2_start = i
        break

# Find end (look for next major component)
detail_view_v2_end = None
for i in range(detail_view_v2_start + 1, len(lines_v2)):
    # Look for WatchlistTab or OptionsScanner or similar
    if (lines_v2[i].startswith('// Watchlist Tab') or 
        lines_v2[i].startswith('// Options Scanner') or
        lines_v2[i].startswith('function WatchlistTab') or
        lines_v2[i].startswith('function OptionsScanner')):
        detail_view_v2_end = i
        break

print(f"app_v2.js DetailView: {detail_view_v2_start} to {detail_view_v2_end}")

# Replace
new_lines = (
    lines_v2[:detail_view_v2_start] +
    ['// TradingView Chart and Detail View Components'] +
    lines[trading_view_start:detail_view_end] +
    [''] +
    lines_v2[detail_view_v2_end:]
)

# Write back
with open('backend/static/app_v2.js', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"✅ Replaced DetailView! Removed {detail_view_v2_end - detail_view_v2_start} lines, added {detail_view_end - trading_view_start} lines")
