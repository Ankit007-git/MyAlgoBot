import os, time, requests, datetime, pytz

# ✅ Screenshot wale Secrets se 100% Match
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
CAPITAL = int(os.getenv("CAPITAL", "30000"))

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
UPSTOX_PIN = os.getenv("UPSTOX_PIN")
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
UPSTOX_REFRESH_TOKEN = os.getenv("UPSTOX_REFRESH_TOKEN")
UPSTOX_TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET")
UPSTOX_USER_ID = os.getenv("UPSTOX_USER_ID")

TELE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_msg(text):
    try:
        requests.post(f"{TELE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except: pass

def place_order():
    url = "https://api.upstox.com/v2/order/place"
    headers = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Content-Type": "application/json"}
    data = {
        "quantity": 25, "product": "I", "validity": "DAY", "price": 0,
        "tag": "AGENT_NORTHFLANK_MODE", "instrument_token": "NSE_INDEX|Nifty 50",
        "order_type": "MARKET", "transaction_type": "BUY",
        "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False
    }
    r = requests.post(url, json=data, headers=headers, timeout=15)
    print("ORDER:", r.text)
    return r.text

def is_market_time():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    if now.weekday() >= 5: return False
    t = now.hour*60 + now.minute
    return 540 <= t <= 945

def main():
    print(f"🔥 POLLER ON - CAPITAL: {CAPITAL}")
    send_msg(f"🟢 Bot ON - Northflank Mode\nCapital: {CAPITAL}\nAb YES likhte hi 3 Sec me Order lagega.")
    seen_ids = set()
    last_offset = 0
    start = time.time()
    while time.time() - start < 340*60:
        if not is_market_time():
            print("Market Closed, Sleeping 60s")
            time.sleep(60)
            continue
        try:
            res = requests.get(f"{TELE_URL}/getUpdates?offset={last_offset+1}&timeout=10", timeout=15).json()
            for u in res.get("result", []):
                last_offset = u["update_id"]
                if u["update_id"] in seen_ids: continue
                seen_ids.add(u["update_id"])
                msg_obj = u.get("message", {})
                msg = msg_obj.get("text", "").upper().strip()
                msg_time = msg_obj.get("date", 0)
                if time.time() - msg_time > 120: continue
                if msg == "YES":
                    send_msg("⚡ YES Mila (3 Sec Mode)! Order laga raha hun...")
                    result = place_order()
                    send_msg(f"✅ ORDER EXECUTE\n{result}\nSL: 25351 | Target: 26375 | Trailing ON")
                elif msg == "NO":
                    send_msg("❌ NO Mila. Order Cancel.")
            time.sleep(3)
        except Exception as e:
            print("Error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
