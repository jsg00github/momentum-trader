
import requests
import json

try:
    print("Sending POST request to /api/scan-options...")
    # Using a small timeout because real scan takes time, but we just want to see if it *starts* or returns *something* structure-wise if we mocked it, 
    # but here we are calling the real one. 
    # Actually, scanning all default tickers might take 10-20s.
    response = requests.post("http://127.0.0.1:8000/api/scan-options", timeout=60)
    
    if response.status_code == 200:
        data = response.json()
        print("Response received.")
        
        if "expert_recommendations" in data:
            print("✅ 'expert_recommendations' field found!")
            recs = data["expert_recommendations"]
            print(f"Found {len(recs)} recommendations.")
            if len(recs) > 0:
                print("Sample Rec:", json.dumps(recs[0], indent=2))
        else:
            print("❌ 'expert_recommendations' field NOT found.")
            print("Keys:", data.keys())
    else:
        print(f"Error: Status {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Exception: {e}")
