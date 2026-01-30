import requests
import json

# Fetch scan results
r = requests.get('http://127.0.0.1:8000/api/scan/progress')
data = r.json()
results = data.get('results', [])

# Write to txt file
with open('scan_results_cache_test.txt', 'w') as f:
    f.write("=" * 60 + "\n")
    f.write("SCAN RESULTS - Cache Fallback Test\n")
    f.write(f"Date: {data.get('last_run', 'N/A')}\n")
    f.write(f"Total Scanned: {data.get('current', 0)} tickers\n")
    f.write(f"Results Found: {len(results)}\n")
    f.write("=" * 60 + "\n\n")
    
    if results:
        f.write("TOP 20 RESULTS (Sorted by Score):\n")
        f.write("-" * 60 + "\n")
        for i, r in enumerate(results[:20], 1):
            f.write(f"{i:2}. {r.get('ticker', '?'):6} | Grade: {r.get('grade', '?'):2} | Score: {r.get('score', 0):5.1f} | RS_SPY: {r.get('rs_spy', 0):+6.2f}%\n")
        f.write("-" * 60 + "\n")
    else:
        f.write("No results found.\n")

print(f"Results saved! Total: {len(results)} stocks found")
print(open('scan_results_cache_test.txt').read())
