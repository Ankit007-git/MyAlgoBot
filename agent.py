import os, json, requests, datetime, time
from tradingview_ta import TA_Handler, Interval

# ============ CONFIG ============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
CAPITAL = 30000
MEMORY_FILE = "memory.json"

# True = Paper Trade (Nakli, Safe) | False = Real Trade (Asli Paisa)
PAPER_TRADE = True

# ============ TELEGRAM ============
def send(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: 
        print("Telegram Token/Chat ID Missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e: print(e)

def load_memory():
    try:
        with open(MEMORY_FILE) as f: return json.load(f)
    except: return {"trades": [], "daily_pnl": {}, "paper_pnl": 0}

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f: json.dump(mem, f, indent=2)

# ============ BRAIN - TRADINGVIEW ============
STOCKS = {
    "BEL": {"tv": "BEL", "upstox": "NSE_EQ|INE263A01024"},
    "HAL": {"tv": "HAL", "upstox": "NSE_EQ|INE066F01012"},
    "RELIANCE": {"tv": "RELIANCE", "upstox": "NSE_EQ|INE002A01018"},
    "TCS": {"tv": "TCS", "upstox": "NSE_EQ|INE467B01029"},
    "INFY": {"tv": "INFY", "upstox": "NSE_EQ|INE009A01021"},
    "HDFCBANK": {"tv": "HDFCBANK", "upstox": "NSE_EQ|INE040A01034"},
    "TATAMOTORS": {"tv": "TATAMOTORS", "upstox": "NSE_EQ|INE155A01022"},
    "SBIN": {"tv": "SBIN", "upstox": "NSE_EQ|INE062A01020"},
    "TITAN": {"tv": "TITAN", "upstox": "NSE_EQ|INE280A01028"},
    "ADANIENT": {"tv": "ADANIENT", "upstox": "NSE_EQ|INE423A01024"},
}

def get_tv_data(symbol):
    try:
        h = TA_Handler(symbol=symbol, screener="india", exchange="NSE", interval=Interval.INTERVAL_15_MINUTES)
        a = h.get_analysis()
        return {"close": a.indicators["close"], "rsi": a.indicators["RSI"], "rec": a.summary["RECOMMENDATION"], "buy": a.summary["BUY"], "sell": a.summary["SELL"]}
    except Exception as e:
        print(f"TV Fail {symbol}: {e}")
        return None

def get_vix():
    try:
        h = TA_Handler(symbol="INDIAVIX", screener="india", exchange="NSE", interval=Interval.INTERVAL_15_MINUTES)
        return h.get_analysis().indicators["close"]
    except: return 14.0

# ============ EXECUTION ============
def place_order_upstox(symbol_key, qty, entry, sl, target):
    if PAPER_TRADE:
        return {"status": "PAPER", "order_id": f"PAPER_{datetime.datetime.now().strftime('%H%M%S')}"}
    try:
        url = "https://api.upstox.com/v2/order/place"
        headers = {"Authorization": f"Bearer {UPSTOX_TOKEN}", "Content-Type": "application/json"}
        payload = {"quantity": qty, "product": "I", "validity": "DAY", "price": entry, "tag": "AGENT_V2", "instrument_token": symbol_key, "order_type": "LIMIT", "transaction_type": "BUY", "disclosed_quantity": 0, "trigger_price": 0, "is_amo": False}
        r = requests.post(url, json=payload, headers=headers, timeout=10).json()
        return {"status": "REAL", "order_id": r.get("data", {}).get("order_id", str(r))}
    except Exception as e:
        return {"status": "FAILED", "order_id": str(e)}

def send_approval_request(trade):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {"inline_keyboard": [[
        {"text": "✅ APPROVE - Order Lagao", "callback_data": f"APPROVE_{trade['name']}"},
        {"text": "❌ REJECT - Mat Lagao", "callback_data": f"REJECT_{trade['name']}"}
    ]]}
    mode = "📝 PAPER TRADE (Nakli)" if PAPER_TRADE else "💰 REAL TRADE (Asli Paisa)"
    text = f"🧠 *AGENT KO TRADE MILA - APPROVAL CHAHIYE*\n\n📈 *{trade['name']} - BUY*\nEntry: {trade['entry']} | SL: {trade['sl']} | Target: {trade['target']}\nQty: {trade['qty']} | Risk: ~300 Rs\nMode: {mode}\n\n*Order lagau? Button dabao - 5 Min hai*"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10).json()
        return r["result"]["message_id"] if r.get("ok") else None
    except: return None

def wait_for_approval(trade, timeout=300):
    send(f"⏳ *Waiting for Approval - {trade['name']}*\n5 Min hai, Telegram pe Button dabao...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    offset = 0
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=15).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    cb = upd["callback_query"]
                    data = cb["data"]
                    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb["id"], "text": "Mil gaya! ✅"}, timeout=5)
                    except: pass
                    if data.startswith("APPROVE"): return True
                    if data.startswith("REJECT"): return False
        except: pass
        time.sleep(3)
    return False

def execute_with_approval(trades_list, mem):
    final = ""
    for t in trades_list:
        send_approval_request(t)
        approved = wait_for_approval(t, timeout=300)
        if approved:
            # TWAP - 2 hisso me Order
            qty1 = max(1, t["qty"] // 2) if t["qty"] > 1 else 1
            qty2 = t["qty"] - qty1
            res1 = place_order_upstox(t["upstox_key"], qty1, t["entry"], t["sl"], t["target"])
            res2 = place_order_upstox(t["upstox_key"], qty2, t["entry"], t["sl"], t["target"])
            send(f"✅ *APPROVED BY YOU*\n{t['name']} Order Lag Gaya!\nOrder ID: {res1['order_id']}\nQty: {t['qty']} ({qty1}+{qty2}) @ {t['entry']}\nSL: {t['sl']} | Target: {t['target']}")
            mem["trades"].append({"date": str(datetime.date.today()), "name": t["name"], "entry": t["entry"], "sl": t["sl"], "target": t["target"], "qty": t["qty"], "status": "open", "mode": "PAPER" if PAPER_TRADE else "REAL", "order_id": res1["order_id"]})
            final += f"\n✅ APPROVED - {t['name']} Done"
        else:
            send(f"❌ *REJECTED / TIMEOUT*\n{t['name']} Order Nahi Lagaya.")
            final += f"\n❌ REJECTED - {t['name']}"
    save_memory(mem)
    return final

# ============ MAIN ============
def main():
    today = datetime.date.today()
    mem = load_memory()
    # Saturday / Sunday - Market Band
    if today.weekday() >= 5:
        send(f"⛔ *AGENT REPORT*\nAaj {today.strftime('%A')} hai, Market Band hai.\nMonday 9:15 ko fir milte hai.")
        return

    vix = get_vix()
    if vix > 22: mood = "🔴 FEAR - Sirf 1 Trade"
    elif vix > 18: mood = "🟡 CAUTIOUS - Halka Trade"
    else: mood = "🟢 BULLISH - Normal Trade"
    max_trades = 1 if vix > 22 else 2

    # Daily Loss Check
    today_str = str(today)
    if mem["daily_pnl"].get(today_str, 0) <= -600:
        send("🛑 *RISK STOP*\nAaj ka Loss 600 Rs ho gaya, Ab koi Trade nahi.")
        return

    candidates = []
    for name, info in STOCKS.items():
        d = get_tv_data(info["tv"])
        if not d: continue
        # Brain Logic: RSI 55-70 + Strong Buy + Price > 100
        if d["rsi"] >= 55 and d["rsi"] <= 70 and d["rec"] in ["STRONG_BUY", "BUY"] and d["buy"] >= 8:
            entry = round(d["close"], 2)
            sl = round(entry * 0.992, 2)  # 0.8% SL
            target = round(entry * 1.025, 2) # 2.5% Target
            risk_per_share = entry - sl
            if risk_per_share <= 0: continue
            qty = int(300 / risk_per_share)
            if qty < 1: continue
            if qty * entry > 15000: qty = int(15000 / entry)
            if qty < 1: continue
            candidates.append({"name": name, "upstox_key": info["upstox"], "entry": entry, "sl": sl, "target": target, "qty": qty, "rsi": round(d["rsi"], 1), "score": d["buy"]})

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)[:max_trades]

    if not candidates:
        send(f"🧠 *ALGO AGENT v2 - ON*\nMood: {mood}\nVIX: {vix:.1f}\n\nAaj koi Strong Setup nahi mila.\nCapital Safe hai. No Trade = Good Trade.")
        return

    # Pehle Summary bhejo
    summary = f"🧠 *ALGO AGENT v2 - ON*\nMood: {mood}\nVIX: {vix:.1f}\n\n🔥 *{len(candidates)} Trade Mile hai - Approval Chahiye*\n"
    for c in candidates:
        summary += f"\n• {c['name']} - Entry {c['entry']} | RSI {c['rsi']} | Qty {c['qty']}"
    send(summary)

    # Ab Approve / Reject wala Flow
    result = execute_with_approval(candidates, mem)
    send(f"🏁 *DAY DONE*\n{result}\n\nMode: {'📝 PAPER' if PAPER_TRADE else '💰 REAL'}\nKal fir milte hai 9:15 AM.")

if __name__ == "__main__":
    main()
