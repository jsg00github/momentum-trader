
import sys
import os

# Add current directory to path so we can import backend
sys.path.append(os.getcwd())

try:
    from backend import alerts, market_data
    
    print("Testing Morning Briefing Generation...")
    status = market_data.get_market_status()
    if "error" in status:
        print("Error fetching status:", status["error"])
        sys.exit(1)
        
    morning_msg = market_data.generate_morning_briefing(status['indices'], status['sectors'])
    print("\n--- GENERATED MORNING MSG ---")
    print(morning_msg)
    print("-----------------------------\n")

    print("Sending Morning Briefing via Telegram...")
    success = alerts.send_scheduled_briefing("MORNING")
    print(f"Morning Sent: {success}")

    print("\nSending Evening Briefing via Telegram...")
    success = alerts.send_scheduled_briefing("EVENING")
    print(f"Evening Sent: {success}")

except ImportError as e:
    print(f"Import Error: {e}")
    print("Make sure you are running this from the root directory.")
except Exception as e:
    print(f"Error: {e}")
