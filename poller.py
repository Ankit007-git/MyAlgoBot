import os
import time
import datetime
import requests
import pytz

# ============ CONFIG - GitHub Secrets Se Aayega ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
UPSTOX_CLIENT_SECRET = os.getenv("UPSTOX_CLIENT_SECRET")
UPSTOX_REFRESH_TOKEN = os.getenv("UPSTOX_REFRESH_TOKEN")
# FIX: http wala - https nahi
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8000")

CAPITAL = 30000
POLL_INTERVAL = 3  # 3 Sec me Check karega

# ============ TELEGRAM FUNCTIONS ============
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def get_telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json().get("result", [])
    except Exception as e:
        print(f"Telegram Get Error: {e}")
        return []

# ============ UPSTOX TOKEN REFRESH ============
def get_fresh_token():
    url = "https://api.upstox.com/v2/login/authorization/token"
    data = {
        "client_id": UPSTOX_CLIENT_ID,
        "client_secret": UPSTOX_CLIENT_SECRET,
        "refresh_token": UPSTOX_REFRESH_TOKEN,
        "grant_type": "refresh_token",
        "redirect_uri": UPSTOX_REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    r = requests.post(url, data=data, headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"Token Refresh Failed: {r.text}")
        return None
    return r.json().get("access_token")

# ============ UPSTOX ORDER ============
def place_order(token, symbol="NIFTY", qty=1):
    url = "https://api.upstox.com/v2/order/place"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
    # Yahan Tera Strategy Wala Symbol / Qty Aayega
    # Abhi Demo ke liye MARKET Order ka Structure hai
    payload = {
        "quantity": qty,
        "product": "I",
        "validity": "DAY",
        "price": 0,
        "tag": "My_algo_Ak",
        "instrument_token": symbol,
        "order_type": "MARKET",
        "transaction_type": "BUY",
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    print(f"Order Response: {r.text}")
    return r.status_code == 200

# ============ WEEKEND SUMMARY - UPSTOX SE REAL DATA ============
def send_weekly_summary(token):
    to_date = datetime.date.today()
    from_date = to_date - datetime.timedelta(days=7)
    url = f"https://api.upstox.com/v2/trade/trades?from_date={from_date}&to_date={to_date}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        trades = r.json().get("data", []) if r.status_code == 200 else []
    except Exception as e:
        print(f"Trades Fetch Error: {e}")
        trades = []

    if not trades:
        msg = (
            "📊 *5 Days Trade Summary*\n"
            "------------------------\n"
            "🗓️ Mon - Fri\n"
            "📈 Total Trades: 0\n"
            "💰 Total P&L: ₹0\n"
            "------------------------\n"
            "😴 Sat-Sun Market OFF Hai\n"
            "Monday 9:15 pe Bot Fir ON Hoga."
        )
        send_telegram(msg)
        return

    total_trades = len(trades)
    total_pnl = 0
    wins = 0
    losses = 0
    for t in trades:
        # Upstox kabhi average_price deta hai, kabhi buy/sell
        buy = float(t.get("buy_price", 0) or t.get("average_price", 0) or 0)
        sell = float(t.get("sell_price", 0) or t.get("average_price", 0) or 0)
        qty = int(t.get("quantity", 0) or 0)
        pnl = (sell - buy) * qty
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

    emoji = "🟢" if total_pnl >= 0 else "🔴"
    msg = (
        "📊 *5 Days Trade Summary - Upstox Real Data*\n"
        "------------------------\n"
        f"🗓️ Mon - Fri (Last 7 Days)\n"
        f"📈 Total Trades: {total_trades}\n"
        f"✅ Win: {wins} | ❌ Loss: {losses}\n"
        f"{emoji} Total P&L: ₹{total_pnl:,.0f}\n"
        "------------------------\n"
        "😴 Sat-Sun Market OFF Hai\n"
        "Monday 9:15 pe Bot Fir ON Hoga."
    )
    send_telegram(msg)
    print(f"Weekly Summary Bhej Diya - P&L: {total_pnl}")

# ============ MARKET TIME CHECK ============
def is_market_time():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 540 <= t <= 945  # 9:00 - 15:45

# ============ MAIN LOOP ============
def main():
    print("Poller Started - Northflank Mode")
    send_telegram(f"🟢 Bot ON - Northflank Mode\nCapital: {CAPITAL}\nAb YES likhte hi 3 Sec me Order lagega.")
    offset = None
    last_summary_sent = None

    while True:
        try:
            ist = pytz.timezone("Asia/Kolkata")
            now = datetime.datetime.now(ist)

            # --- SAT-SUN : SUMMARY BHEJ KE SO JAO ---
            if now.weekday() >= 5:
                today_str = now.strftime("%Y-%m-%d")
                # Ek Din me 1 Baar hi Summary Bhejna hai, Baar-Baar Nahi
                if last_summary_sent != today_str:
                    token = get_fresh_token()
                    if token:
                        send_weekly_summary(token)
                        last_summary_sent = today_str
                    else:
                        send_telegram("⚠️ Weekend Summary Fail: Token Refresh Nahi Hua. Redirect URI Check Karo.")
                        last_summary_sent = today_str
                print("Weekend Hai, 1 Ghanta So Raha Hu...")
                time.sleep(3600)
                continue

            # --- MON-FRI BUT MARKET BAND : SO JAO ---
            if not is_market_time():
                print("Market Closed, Sleeping 60s")
                time.sleep(60)
                continue

            # --- MARKET KHULA HAI : TELEGRAM SUNO ---
            updates = get_telegram_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                msg_obj = u.get("message", {})
                text = msg_obj.get("text", "").strip().upper()

                if text == "YES":
                    send_telegram("✅ YES Mila. Order Laga Raha Hu...")
                    token = get_fresh_token()
                    if token and place_order(token):
                        send_telegram("✅ Order Lag Gaya - Upstox Me Check Karo.")
                    else:
                        send_telegram("❌ Order Fail Hua. Token / Upstox Check Karo.")

                elif text == "NO":
                    send_telegram("❌ NO Mila. Order Cancel.")

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
