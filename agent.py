import os
import requests
from datetime import datetime, timezone, timedelta

# --- 1. SAB NAAM KA FIX - Jo bhi Naam hoga, ye dhoond lega ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHATID") or ""
UPSTOX_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_TOKEN") or ""

IST = timezone(timedelta(hours=5, minutes=30))

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"❌ MISSING: TOKEN len={len(TELEGRAM_TOKEN)} CHAT len={len(CHAT_ID)}")
        print("CHECK: Secrets me TELEGRAM_TOKEN / TELEGRAM_BOT_TOKEN aur TELEGRAM_CHAT_ID hai ya nahi?")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
        print(f"Telegram Status: {r.status_code} - {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

def main():
    now = datetime.now(IST)
    day = now.strftime("%A")
    print(f"Running... Day={day} Time={now.strftime('%H:%M')} TOKEN len={len(TELEGRAM_TOKEN)} CHAT len={len(CHAT_ID)} UPSTOX len={len(UPSTOX_TOKEN)}")

    # --- 2. SATURDAY / SUNDAY FIX ---
    if day in ["Saturday", "Sunday"]:
        send_telegram(f"⛔ *AGENT REPORT*\n\nAaj {day} hai, Market Band hai.\nAgent sahi chal raha hai ✅\nTime: {now.strftime('%d %b %Y, %I:%M %p')}")
        return

    # --- 3. UPSTOX FAIL HONE PAR BHI TELEGRAM AAYEGA ---
    price_msg = "Data nahi mila"
    try:
        if not UPSTOX_TOKEN:
            price_msg = "Upstox Token Missing hai"
        else:
            headers = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Accept": "application/json"}
            # Nifty 50 LTP
            r = requests.get("https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_INDEX|Nifty 50", headers=headers, timeout=15)
            if r.status_code == 200:
                price = r.json().get("data", {}).get("NSE_INDEX|Nifty 50", {}).get("last_price", "N/A")
                price_msg = f"Nifty 50: {price}"
            else:
                price_msg = f"Upstox Error {r.status_code} - Token Expire ho sakta hai"
    except Exception as e:
        price_msg = f"Upstox Error: {e}"

    send_telegram(f"✅ *AGENT REPORT - LIVE*\n\n{price_msg}\nDay: {day}\nTime: {now.strftime('%I:%M %p')}")

if __name__ == "__main__":
    main()
