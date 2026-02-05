import requests
import sys

BASE_URL = "http://127.0.0.1:8000"
USER_EMAIL = "admin@example.com"
USER_PASS = "securepassword123"

def print_result(step, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {step}: {details}")
    if not success:
        sys.exit(1)

def main():
    print(f"Running System Verification against {BASE_URL}...\n")

    # 1. Register
    try:
        reg_payload = {"email": USER_EMAIL, "password": USER_PASS}
        # Note: Depending on implementation, register might return 201 or 200
        resp = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
        
        # Determine success (created or already exists)
        if resp.status_code == 200 or resp.status_code == 201:
            print_result("User Registration", True, "User created successfully")
        elif resp.status_code == 400 and "already registered" in resp.text:
            print_result("User Registration", True, "User already exists (skipping registration)")
        else:
            print_result("User Registration", False, f"Status: {resp.status_code}, Body: {resp.text}")
            
    except Exception as e:
        print_result("User Registration", False, f"Exception: {str(e)}")

    # 2. Login
    token = None
    try:
        login_payload = {"username": USER_EMAIL, "password": USER_PASS} # OAuth2PasswordRequestForm expects username
        # Our endpoint expects JSON or Form data? 
        # Checking auth.py: router.post("/login", response_model=Token)
        # Usually OAuth2PasswordRequestForm expects form data.
        # Let's try Form Data first which is standard for FastAPI OAuth2
        resp = requests.post(f"{BASE_URL}/api/auth/login", data=login_payload)
        
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print_result("User Login", True, "Token acquired")
        else:
            # Fallback: maybe it expects JSON? (Less likely for standard OAuth2 but possible in custom impl)
            resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS})
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                print_result("User Login", True, "Token acquired (via JSON)")
            else:
                print_result("User Login", False, f"Status: {resp.status_code}, Body: {resp.text}")

    except Exception as e:
        print_result("User Login", False, f"Exception: {str(e)}")

    if not token:
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Trade
    try:
        # Check current trades count
        resp = requests.get(f"{BASE_URL}/api/trades/list", headers=headers)
        initial_count = len(resp.json()) if resp.status_code == 200 else 0

        trade_payload = {
            "ticker": "TEST-BTC",
            "entry_date": "2025-01-10",
            "entry_price": 50000.0,
            "shares": 1,
            "direction": "BUY",
            "status": "OPEN",
            "strategy": "MOMENTUM_TEST"
        }
        resp = requests.post(f"{BASE_URL}/api/trades/add", json=trade_payload, headers=headers)
        
        if resp.status_code == 200:
            print_result("Create Trade", True, f"Trade created. ID: {resp.json().get('trade_id')}")
        else:
            print_result("Create Trade", False, f"Status: {resp.status_code}, Body: {resp.text}")

    except Exception as e:
        print_result("Create Trade", False, f"Exception: {str(e)}")

    # 4. Verify Persistence
    try:
        resp = requests.get(f"{BASE_URL}/api/trades/list", headers=headers)
        trades_data = resp.json()
        trades = trades_data.get('trades', [])
        
        found = any(t['ticker'] == 'TEST-BTC' for t in trades)
        if found:
            print_result("Verify Persistence", True, f"Found TEST-BTC in {len(trades)} trades")
        else:
            print_result("Verify Persistence", False, "TEST-BTC not found in trade list")

    except Exception as e:
        print_result("Verify Persistence", False, f"Exception: {str(e)}")

    # 5. Verify Scanner Endpoint
    try:
        resp = requests.get(f"{BASE_URL}/api/scan/progress", headers=headers)
        if resp.status_code == 200:
            print_result("Scanner Health", True, "Scanner endpoint reachable")
        else:
            print_result("Scanner Health", False, f"Status: {resp.status_code}")
    except Exception as e:
        print_result("Scanner Health", False, f"Exception: {str(e)}")

    # 6. Verify Argentina Journal
    try:
        resp = requests.get(f"{BASE_URL}/api/argentina/positions", headers=headers)
        if resp.status_code == 200:
            print_result("Argentina Journal", True, "Endpoint reachable")
        else:
            print_result("Argentina Journal", False, f"Status: {resp.status_code}")
    except Exception as e:
        print_result("Argentina Journal", False, f"Exception: {str(e)}")

    # 7. Verify Crypto Journal
    try:
        resp = requests.get(f"{BASE_URL}/api/crypto/positions", headers=headers)
        if resp.status_code == 200:
            print_result("Crypto Journal", True, "Endpoint reachable")
        else:
            print_result("Crypto Journal", False, f"Status: {resp.status_code}")
    except Exception as e:
        print_result("Crypto Journal", False, f"Exception: {str(e)}")

if __name__ == "__main__":
    main()
