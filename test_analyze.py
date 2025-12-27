import requests
import json

# Test the analyze endpoint
tickers = ['VSTS', 'CSTS']

for ticker in tickers:
    print(f"\n{'='*50}")
    print(f"Testing {ticker}")
    print('='*50)
    
    try:
        r = requests.post('http://127.0.0.1:8000/api/analyze', json={'ticker': ticker}, timeout=10)
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            if 'error' in data:
                print(f"Error: {data['error']}")
            else:
                metrics = data.get('metrics', {})
                print(f"Metrics:")
                print(f"  entry: {metrics.get('entry')}")
                print(f"  target: {metrics.get('target')}")
                print(f"  stop_loss: {metrics.get('stop_loss')}")
                print(f"  is_bull_flag: {metrics.get('is_bull_flag')}")
                print(f"Chart data: {len(data.get('chart_data', []))} points")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"Exception: {e}")
