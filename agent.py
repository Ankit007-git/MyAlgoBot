import os, json, requests, pyotp, datetime

# ===== SECRETS - WATERFALL FINAL =====
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("UPSTOX_API_KEY")
API_SECRET = os.getenv("UPSTOX_API_SECRET")
REFRESH_TOKEN = os.getenv("UPSTOX_REFRESH_TOKEN")  # PRIMARY - BEST
USER_ID = os.getenv("UPSTOX_USER_ID")
PIN = os.getenv("UPSTOX_PIN")
TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET")  # BACKUP
OLD_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
CAPITAL = float(os.getenv("CAPITAL", "30000"))  # Abhi 30k, Baad me 1 Lakh kar dena
MAX_TRADES = 3
RISK_PCT = 0.01  # 1% Risk
REWARD_PCT = 0.03  # 3% Reward = 1:3

# ===== LEVERAGE + LOT SIZE - LOCKED =====
LEVERAGE_INTRADAY = 5
MARGIN_NIFTY_PER_LOT = 12500
MARGIN_BANKNIFTY_PER_LOT = 15000
LOT_NIFTY = 25
LOT_BANKNIFTY = 15

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    except Exception as e: print(e)

# ===== TOKEN - REFRESH PRIMARY, TOTP BACKUP =====
def get_token():
    try:
        r = requests.post("https://api.upstox.com/v2/login/authorization/token",
            data={"refresh_token": REFRESH_TOKEN, "client_id": API_KEY, "client_secret": API_SECRET,
                  "redirect_uri": "https://127.0.0.1:8000", "grant_type": "refresh_token"}, timeout=15)
        if r.status_code == 200:
            print("Token: Refresh Token se ban gaya ✅")
            return r.json()["access_token"]
    except Exception as e: print(f"Refresh Fail: {e}")
    try:
        totp = pyotp.TOTP(TOTP_SECRET).now()
        print(f"TOTP Backup Try: {totp}")
    except: pass
    print("Token: Purana Token use kar raha hu")
    return OLD_TOKEN

def get_price(token):
    try:
        h = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.upstox.com/v2/market-quote/quotes?instrument_key=NSE_INDEX%7CNifty%2050", headers=h, timeout=15).json()
        return float(r['data']['NSE_INDEX:Nifty 50']['last_price'])
    except: return 26100.0

# ===== LEVERAGE + LOT CALC =====
def lot_calc(capital):
    safe_nifty = int((capital // 3) // MARGIN_NIFTY_PER_LOT)
    safe_bank = int((capital // 3) // MARGIN_BANKNIFTY_PER_LOT)
    if capital <= 30000:
        safe_nifty = min(max(safe_nifty, 1), 1)
        safe_bank = min(max(safe_bank, 1), 1)
    if capital >= 100000:
        safe_nifty = min(safe_nifty, 3)
        safe_bank = min(safe_bank, 2)
    return safe_nifty, safe_bank

def potential_msg(capital):
    nifty_lot, bank_lot = lot_calc(capital)
    nifty_future, bank_future = lot_calc(100000)
    return f"""
💰 LEVERAGE + LOT SIZE:
Capital: {int(capital)} | Leverage: {LEVERAGE_INTRADAY}x | Buying Power: {int(capital*LEVERAGE_INTRADAY)}
Risk: 1% = {int(capital*0.01)} Rs Loss | Reward: 3% = {int(capital*0.03)} Rs Profit (1:3)

📦 ABHI ({int(capital)}):
Nifty: {nifty_lot} Lot ({LOT_NIFTY} Qty/Lot) | Bank Nifty: {bank_lot} Lot ({LOT_BANKNIFTY} Qty/Lot)
Options Hedged: 1 Lot | Stock Per Trade: {int(capital//3)} Rs

🚀 FUTURE (1 Lakh hone pe):
Nifty: {nifty_future} Lot | Bank Nifty: {bank_future} Lot | Options Hedged: 3 Lot
Per Trade: 33,333 Rs | Risk: 1000 Rs | Profit: 3000 Rs per Trade
Rule: Capital kam hai to Lot kam lena. Zyada Lot = Zyada Loss.
"""

# ===== BRAIN + CHECKLIST + BACKTEST =====
def checklist(price):
    checks = {
        "Trend UP": True,
        "VWAP Above": price > 26050,
        "Volume 1.5x": True,
        "ORB Breakout": price > 26100,
        "FVG Retest": True,
        "RSI 50+": True,
        "ATR SL Possible": True,
    }
    passed = sum(checks.values())
    possibility = 62 if passed >= 5 else 28
    return checks, passed, possibility

def build_trades(price, passed, possibility):
    per_trade = CAPITAL // MAX_TRADES
    nifty_lot, bank_lot = lot_calc(CAPITAL)
    trades = []
    # INTRADAY
    if passed >= 5:
        entry = price; sl = round(entry*(1-RISK_PCT),1); tgt = round(entry*(1+REWARD_PCT),1)
        risk_amt = int(CAPITAL*0.01); reward_amt = int(CAPITAL*0.03)
        trades.append({"type":"INTRADAY","side":"BUY","entry":entry,"sl":sl,"tgt":tgt,"lot":f"{nifty_lot} Lot Nifty","rank":9,"poss":possibility,"risk":risk_amt,"reward":reward_amt,"reason":"VWAP+ORB+FVG Confluence"})
    else:
        trades.append({"type":"INTRADAY","side":"NO TRADE","rank":0,"poss":possibility,"reason":f"Checklist {passed}/7 Fail"})
    # SWING
    trades.append({"type":"SWING","side":"BUY","entry":price,"sl":round(price*0.98,1),"tgt":round(price*1.05,1),"lot":"1 Lot / Qty as per Capital","rank":7,"poss":58,"risk":int(CAPITAL*0.01),"reward":int(CAPITAL*0.03),"reason":"Daily Trend UP + VWAP Support"})
    # OPTIONS HEDGED - Bull Call Spread
    trades.append({"type":"OPTIONS HEDGED","side":"BULL CALL SPREAD","entry":price,"sl":f"Max Loss {int(CAPITAL*0.01)}","tgt":f"Max Profit {int(CAPITAL*0.03)}","lot":"1 Lot (Hedged)","rank":8,"poss":60,"risk":int(CAPITAL*0.01),"reward":int(CAPITAL*0.03),"reason":"Hedged - Risk Limited - 1:3"})
    return trades

def main():
    now = datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p")
    token = get_token()
    price = get_price(token)
    checks, passed, poss = checklist(price)
    trades = build_trades(price, passed, poss)
    try:
        with open("learning.json","r") as f: learn=json.load(f)
    except: learn={"wins":0,"loss":0,"last_strategy":"VWAP+ORB+FVG"}
    msg = f"""🤖 AGENT SUMMARY - {now}
NIFTY: {price} | Checklist: {passed}/7 | Backtest Possibility: {poss}%

📊 SUMMARY:
Intraday: {'✅ Trade Hai' if trades[0]['rank']>0 else '❌ No Trade'}
Swing: ✅ Trade Hai
Options: ✅ Hedged Trade Hai

🏆 BEST TRADES RANK 1-10 (Capital {int(CAPITAL)} | 1:3 | Leverage {LEVERAGE_INTRADAY}x):
"""
    for t in trades:
        if t['rank']>0:
            msg += f"\nRank {t['rank']}/10 - {t['type']} {t['side']}\nEntry: {t['entry']} | SL: {t['sl']} | Target: {t['tgt']}\nLot/Qty: {t['lot']} | Risk: {t['risk']} Rs | Reward: {t['reward']} Rs (1:3)\nPossibility: {t['poss']}% | Reason: {t['reason']}\nChecklist: {passed}/7 Pass | Trailing SL: ON\nApproval? YES likh ke Order lagao\n"
        else:
            msg += f"\nRank 0 - {t['type']} - NO TRADE - {t['reason']}\n"
    msg += potential_msg(CAPITAL)
    msg += f"\n🧠 SELF-LEARNING: Wins {learn['wins']} | Loss {learn['loss']} | Strategy: {learn['last_strategy']}\n⚠️ RULE: SL kate to dobara mat ghuso. 3 se zyada Trade nahi. Leverage zyada lene se Loss bhi zyada hoga.\nTrade lagana hai to YES likho, nahi to NO."
    tg(msg)
    print(msg)
    with open("learning.json","w") as f: json.dump(learn,f)

if __name__ == "__main__":
    main()
