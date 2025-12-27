import requests
import json

def verify():
    url = "http://127.0.0.1:8000/api/trades/add"
    
    # 1. Existing trade known to have SL (SMC, id 6, SL 23.0)
    # We will simply add a new one for SMC with no SL.
    
    payload = {
        "ticker": "SMC",
        "entry_date": "2025-12-23",
        "entry_price": 25.50,
        "shares": 5,
        "direction": "BUY",
        "status": "OPEN",
        "stop_loss": None,
        "target": None
    }
    
    print(f"Sending payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            new_id = data.get("trade_id")
            print(f"New Trade ID: {new_id}")
            
            # Now fetch this trade to check its SL
            # We don't have a single trade fetch endpoint easily exposed maybe?
            # Actually /api/trades/list returns all. Let's find it there.
            
            list_resp = requests.get("http://127.0.0.1:8000/api/trades/list", params={"ticker": "SMC"})
            trades = list_resp.json()["trades"]
            
            new_trade = next((t for t in trades if t["id"] == new_id), None)
            
            if new_trade:
                print(f"New Trade SL: {new_trade['stop_loss']}")
                if new_trade['stop_loss'] == 23.0:
                    print("SUCCESS: SL inherited correctly!")
                else:
                    print(f"FAILURE: SL is {new_trade['stop_loss']}, expected 23.0")
            else:
                print("FAILURE: New trade not found in list")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
