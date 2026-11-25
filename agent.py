import os
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

# Abhi ke liye Test Message - Baad me isme Signal Logic lagayenge
today = datetime.now().strftime("%d %b %Y, %I:%M %p")
msg = f"✅ *MyAlgoBot Live Hai!*\n\n📅 Date: {today}\n🤖 Status: Auto System ON Hai\n\nKal se Roz 9:30 AM pe Yahi se Signal Aayega."
send_msg(msg)
print("Message Bhej Diya")
