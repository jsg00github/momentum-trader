import requests
r = requests.post('http://127.0.0.1:8000/api/analyze', json={'ticker': 'AGEN'})
data = r.json()
print(f'Symbol: {data.get("metrics", {}).get("symbol")}')
print(f'Current Close: ${data.get("metrics", {}).get("current_close")}')
print(f'Chart points: {len(data.get("chart_data", []))}')
if data.get('chart_data'):
    last = data['chart_data'][-1]
    print(f'Last date: {last.get("date")}')
    print(f'Last close: ${last.get("close")}')
