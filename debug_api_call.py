
import requests
import json

def debug_api():
    url = "http://127.0.0.1:8000/api/analyze"
    payload = {"ticker": "DXYZ"}
    
    print(f"POST {url} with {payload}")
    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            data = res.json()
            print("Response Received.")
            # detailed check
            if "chart_data" in data and len(data["chart_data"]) > 0:
                last_pt = data["chart_data"][-1]
                print(f"Last Point Date: {last_pt.get('date')}")
                print(f"Last Point Close: {last_pt.get('close')}")
                
                # Check metrics if available
                if "metrics" in data:
                    print(f"Metrics Current Close: {data['metrics'].get('current_close')}")
            else:
                print("No chart_data in response!")
                print(data)
        else:
            print(f"Failed: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    debug_api()
