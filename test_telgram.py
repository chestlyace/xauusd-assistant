import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

print(f"Testing Telegram...")
print(f"Bot Token: {BOT_TOKEN[:20]}..." if BOT_TOKEN else "❌ NO TOKEN")
print(f"Chat ID: {CHAT_ID}\n")

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Missing credentials in .env file!")
    exit(1)

# Test message
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    'chat_id': CHAT_ID,
    'text': '🧪 Test message from XAUUSD Trading Assistant!\n\nIf you see this, Telegram is working! ✅'
}

try:
    response = requests.post(url, json=payload, timeout=30)
    
    if response.status_code == 200:
        print("✅ SUCCESS! Check your Telegram - you should have received a test message!")
    else:
        print(f"❌ Failed with status {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")