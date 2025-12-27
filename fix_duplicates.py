# Fix duplicate functions by removing the old ones
with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all TradingViewChart and MetricCard occurrences
tradingview_lines = []
metriccard_lines = []

for i, line in enumerate(lines):
    if 'function TradingViewChart' in line:
        tradingview_lines.append(i)
    if 'function MetricCard' in line:
        metriccard_lines.append(i)

print(f"TradingViewChart at lines: {[l+1 for l in tradingview_lines]}")
print(f"MetricCard at lines: {[l+1 for l in metriccard_lines]}")

# We want to keep the SECOND occurrences (the ones from app.js we just added)
# So we need to remove the FIRST occurrences

# Mark lines to remove
lines_to_remove = set()

if len(tradingview_lines) >= 2:
    # Remove first TradingViewChart (find its end)
    start = tradingview_lines[0]
    # Find end of function (look for closing brace at same indentation)
    brace_count = 0
    started = False
    for i in range(start, len(lines)):
        if '{' in lines[i]:
            brace_count += lines[i].count('{')
            started = True
        if '}' in lines[i]:
            brace_count -= lines[i].count('}')
        if started and brace_count == 0:
            # Found end
            for j in range(start, i+1):
                lines_to_remove.add(j)
            print(f"Removing old TradingViewChart: lines {start+1} to {i+1}")
            break

if len(metriccard_lines) >= 2:
    # Remove first MetricCard
    start = metriccard_lines[0]
    # Find end (it's short, usually ~10 lines)
    brace_count = 0
    started = False
    for i in range(start, min(start + 20, len(lines))):
        if '{' in lines[i]:
            brace_count += lines[i].count('{')
            started = True
        if '}' in lines[i]:
            brace_count -= lines[i].count('}')
        if started and brace_count == 0:
            for j in range(start, i+1):
                lines_to_remove.add(j)
            print(f"Removing old MetricCard: lines {start+1} to {i+1}")
            break

# Write filtered lines
new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]

with open('backend/static/app_v2.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n✅ Removed {len(lines_to_remove)} duplicate lines")
print(f"New file size: {len(new_lines)} lines (was {len(lines)})")
