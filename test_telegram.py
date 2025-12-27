"""Quick test for Telegram alerts"""
from backend import alerts

chat_id = "1062512792"
message = "🔔 <b>Test Alert</b>\n\nYour Telegram alerts are configured correctly!"

print(f"Sending test to chat_id: {chat_id}")
print(f"BOT_TOKEN loaded: {alerts.BOT_TOKEN[:20]}..." if alerts.BOT_TOKEN else "❌ BOT_TOKEN not loaded")

success = alerts.send_telegram(chat_id, message)
print(f"Result: {'✅ Success!' if success else '❌ Failed'}")
