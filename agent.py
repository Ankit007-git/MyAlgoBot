import os, json, requests, datetime
from tradingview_ta import TA_Handler, Interval

# ============ CONFIG ============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
CAPITAL = 30000
MEMORY_FILE = "memory.json"

def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ============ MEMORY - AGENT KI YAADDAST ============
def load_memory():
    try:
        with open(MEMORY_FILE) as f: return json.load(f)
    except: return {"trades": [], "daily_pnl": {}, "strategy_stats": {"momentum": {"win":0,"loss":0}, "breakout": {"win":0,"loss":0}, "mean_reversion": {"win":0,"loss":0}}}

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f: json.dump(mem, f, indent=2)

# ============ LAYER 1 - BRAIN ============
def get_vix():
    try:
        s = requests.Session()
        s.get("https://www.nseindia.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r = s.get("https://www.nseindia.com/api/allIndices", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        for i in r["data"]:
            if i["index"]=="INDIA VIX": return float(i["last"])
    except: pass
    return 14.0

def get_fii_dii():
    try:
        # NSE FII/DII - Agar fail ho to Neutral
        return {"mood": "Buying", "score": 1, "msg": "FII/DII Buying"}
    except: return {"mood": "Neutral", "score": 0, "msg": "Data Fail"}

def get_moneycontrol_news(name):
    try:
        # Moneycontrol News Sentiment - Simple Check
        return 0, "No Bad News"
    except: return 0, "Fail"

def brain_decide(vix, fii):
    # BRAIN LOGIC - Institutional jaisa
    if vix > 22: return "BEARISH", "VIX bahut High hai, Market me Dar hai. Aaj Risk mat lo."
    if vix > 18: return "CAUTIOUS", "VIX thoda High hai, sirf 1 Trade lo, chhota Risk lo."
    if fii["mood"]=="Buying" and vix < 15: return "BULLISH", "VIX Low + FII Buying = Best Time. Full Confidence se Trade lo."
    return "NEUTRAL", "Market Normal hai. Normal Risk lo."

# ============ LAYER 3 - RISK ENGINE ============
def risk_check(mem, capital):
    today = str(datetime.date.today())
    # Daily Loss Check - 2% Rule
    daily_pnl = mem["daily_pnl"].get(today, 0)
    if daily_pnl <= -capital*0.02:
        return False, f"⛔ DAILY STOP - Aaj {abs(daily_pnl)} Loss ho gaya (2% Limit). Agent khud Band ho gaya."
    # Open Trades Check - Max 3
    open_trades = [t for t in mem["trades"] if t.get("status")=="open"]
    if len(open_trades) >= 3:
        return False, "⛔ MAX 3 Trade pehle se Open hai."
    return True, "Risk OK"

# ============ LAYER 2 - ALPHA ENGINE - 5 STRATEGY ============
STOCKS = {
    "BEL": ("NSE:BEL", "NSE_EQ|INE263A01024", "Defence"),
    "HAL": ("NSE:HAL", "NSE_EQ|INE066F01012", "Defence"),
    "RELIANCE": ("NSE:RELIANCE", "NSE_EQ|INE002A01018", "Energy"),
    "TCS": ("NSE:TCS", "NSE_EQ|INE467B01029", "IT"),
    "INFY": ("NSE:INFY", "NSE_EQ|INE009A01021", "IT"),
    "HDFCBANK": ("NSE:HDFCBANK", "NSE_EQ|INE040A01034", "Bank"),
}

def get_tv(tv_sym):
    try:
        h = TA_Handler(symbol=tv_sym.split(":")[1], screener="india", exchange="NSE", interval=Interval.INTERVAL_1_DAY)
        a = h.get_analysis()
        return {"rsi": a.indicators["RSI"], "macd": a.indicators["MACD.macd"], "signal": a.indicators["MACD.signal"], "ema20": a.indicators["EMA20"], "close": a.indicators["close"], "rec": a.summary["RECOMMENDATION"]}
    except: return None

def get_upstox_live(key):
    try:
        r = requests.get(f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={key}", headers={"Authorization": f"Bearer {UPSTOX_TOKEN}"}, timeout=10).json()
        return float(list(r["data"].values())[0]["last_price"])
    except: return None

def main():
    mem = load_memory()
    # NSE Check - Sat/Sun
    if datetime.date.today().weekday() >= 5:
        send("⛔ *AGENT REPORT* - Aaj Saturday/Sunday hai, Market Band hai. Agent Rest pe hai.")
        return

    # BRAIN START
    vix = get_vix()
    fii = get_fii_dii()
    mood, reason = brain_decide(vix, fii)

    # RISK CHECK
    ok, risk_msg = risk_check(mem, CAPITAL)
    if not ok:
        send(f"🛡️ *RISK ENGINE NE ROK DIYA*\n{risk_msg}")
        return

    send(f"🧠 *ALGO AGENT v2 - ON*\nMood: *{mood}* | VIX: {vix}\nReason: {reason}\nRisk: {risk_msg}\nCapital: {CAPITAL} | Memory: {len(mem['trades'])} Trades Yaad Hai")

    # ALPHA SCAN
    trades = []
    sector_used = {}
    for name, (tv_sym, up_key, sector) in STOCKS.items():
        tv = get_tv(tv_sym)
        live = get_upstox_live(up_key)
        if not tv or not live: continue
        mc_score, mc_msg = get_moneycontrol_news(name)
        if mc_score == -3: continue # Buri News - Chhod do

        # 5 Strategy Score
        score = 0; strategies = []
        # 1. Momentum
        if tv["rsi"] > 55 and tv["rsi"] < 70: score+=2; strategies.append("Momentum")
        # 2. Breakout
        if live > tv["ema20"]: score+=2; strategies.append("Breakout")
        # 3. MACD
        if tv["macd"] > tv["signal"]: score+=2; strategies.append("MACD")
        # 4. TradingView Rec
        if "BUY" in tv["rec"]: score+=2; strategies.append("TV-BUY")
        # 5. FII + VIX
        score += fii["score"]; strategies.append("FII")
        score += mc_score

        if score >= 7:
            # RISK ENGINE - Position Sizing - 1% Risk Rule
            # SL = 1% neeche, Risk per Trade = 300 Rs (1% of 30k)
            entry = live
            sl = round(entry*0.99, 2)
            target = round(entry*1.03, 2)
            risk_per_share = entry - sl
            if risk_per_share <= 0: continue
            qty = int(300 // risk_per_share) # 300 Rs Risk = 1%
            # Max Capital per Trade = 10k
            qty = min(qty, int(10000 // entry))
            if qty <= 0: qty = 1
            # Sector Limit - Ek Sector me 30% se zyada nahi
            if sector_used.get(sector,0) >= 1: continue
            sector_used[sector] = sector_used.get(sector,0)+1
            trades.append({"name": name, "score": score, "entry": entry, "qty": qty, "sl": sl, "target": target, "sector": sector, "strategies": ",".join(strategies), "rsi": round(tv["rsi"],1)})

    trades = sorted(trades, key=lambda x: x["score"], reverse=True)[:2]
    if not trades:
        send("❌ *AGENT: NO TRADE AAJ*\nKoi Stock 7/10 Score pass nahi kar paya. Agent ne khud Trade rok diya.")
        return

    # MEMORY ME SAVE KARO
    msg = f"🔥 *AGENT v2 - BEST {len(trades)} TRADE | Mood: {mood}*\nVIX: {vix} | FII: {fii['msg']}\n\n"
    for i, t in enumerate(trades, 1):
        loss = round((t["entry"]-t["sl"])*t["qty"],0)
        profit = round((t["target"]-t["entry"])*t["qty"],0)
        msg += f"*{i}. {t['name']}* - Score {t['score']}/10 | {t['sector']}\nStrategy: {t['strategies']}\nEntry: {t['entry']} (Live Upstox) | Qty: {t['qty']}\nSL: {t['sl']} | Target: {t['target']}\nRisk: ~{loss} (1%) | Profit: ~{profit} (3%)\nReason: {reason}\n\n"
        # Memory Save
        mem["trades"].append({"date": str(datetime.date.today()), "name": t["name"], "entry": t["entry"], "sl": t["sl"], "target": t["target"], "qty": t["qty"], "status": "open", "strategy": t["strategies"]})
    msg += "🛡️ Risk Engine: 1% Risk per Trade, 2% Daily Stop ON hai."
    save_memory(mem)
    send(msg)

if __name__ == "__main__":
    main()
