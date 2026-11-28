import os, time, asyncio, datetime, requests, pyotp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== SECRET WALE NAAM - BILKUL SAME =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
UPSTOX_USER_ID = os.getenv("UPSTOX_USER_ID")
UPSTOX_PIN = os.getenv("UPSTOX_PIN")
UPSTOX_TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET")
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

# ===== STRATEGY - TERA LOCK WALA =====
CAPITAL = 30000
MAX_TRADES = 3
PER_TRADE_CAPITAL = CAPITAL // MAX_TRADES  # 10k
RISK_PCT = 0.01
REWARD_PCT = 0.03  # 1:3

STOCKS = ["HAL.NS","TRENT.NS","RELIANCE.NS","TCS.NS","ICICIBANK.NS","BEL.NS","TITAN.NS","BAJFINANCE.NS","HCLTECH.NS","ADANIPORTS.NS"]

trades_today = []
total_pnl = 0
bot_app = None

def send_telegram_sync(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(e)

def get_data(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6mo&interval=1d"
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
    res = r.json()['chart']['result'][0]
    q = res['indicators']['quote'][0]
    return q['close'], q['high'], q['low'], q['open'], q['volume']

def ema(prices, p):
    k=2/(p+1); e=prices[0]; out=[]
    for x in prices:
        e=x*k+e*(1-k) if x else e
        out.append(e)
    return out

def rsi(prices, period=14):
    gains=[]; losses=[]
    for i in range(1,len(prices)):
        d=prices[i]-prices[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    if len(gains)<period: return 50
    ag=sum(gains[-period:])/period; al=sum(losses[-period:])/period
    if al==0: return 100
    return 100-(100/(1+ag/al))

def deep_check(sym):
    try:
        closes,highs,lows,opens,vols = get_data(sym)
        closes=[c for c in closes if c is not None]
        highs=[h for h in highs if h is not None]
        lows=[l for l in lows if l is not None]
        opens=[o for o in opens if o is not None]
        vols=[v for v in vols if v is not None]
        price=closes[-1]
        e20=ema(closes,20); e50=ema(closes,50)
        prev_high=max(highs[-21:-1])
        avg_vol=sum(vols[-21:-1])/20
        today_vol=vols[-1]
        vwap=sum([closes[-5+i]*vols[-5+i] for i in range(5)])/sum(vols[-5:])
        rs=rsi(closes)
        gap=(opens[-1]-closes[-2])/closes[-2]*100
        if abs(gap)>1.5: return None
        wick=(highs[-1]-price)/highs[-1]*100
        if price>closes[-2] and today_vol<avg_vol: return None
        if wick>1.5: return None
        score=0
        if price>e20[-1]>e50[-1]: score+=2
        if price>prev_high: score+=2
        if today_vol>avg_vol*1.5: score+=2
        if price>vwap: score+=1
        if 55<=rs<=72: score+=1
        if abs(gap)<0.8: score+=1
        score+=1
        return (score, price) if score>=7 else None
    except:
        return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tu jab bhi /start likhega, ye chalega
    if len(trades_today)==0:
        msg = "📊 FULL DAY SUMMARY\n\n❌ No New Trade\nAaj abhi tak koi 7/10 Score wala Trade nahi bana.\nMarket 3:30 PM tak khula hai, Scan chal raha hai."
    else:
        msg = f"📊 FULL DAY SUMMARY\n\nTotal Trades: {len(trades_today)}\nTotal P&L (Expected): {total_pnl} Rs\n\n"
        for t in trades_today:
            msg += f"{t}\n"
    await update.message.reply_text(msg)

async def main_loop():
    global total_pnl
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    # TOTP Auto Login Info
    try:
        otp = pyotp.TOTP(UPSTOX_TOTP_SECRET).now()
        print(f"TOTP OK: {otp} | USER: {UPSTOX_USER_ID}")
    except Exception as e:
        print(f"TOTP Error: {e}")

    await bot_app.bot.send_message(chat_id=CHAT_ID, text="🚀 Bot ON - 9:15 se 3:30 tak Scan kar raha hu\nCapital 30k | Max 3 Trade | 1:3\n/start likh ke kabhi bhi Summary le sakte ho.")

    already_sent = False
    while True:
        now = datetime.datetime.now()
        if now.hour >= 15 and now.minute >= 30:
            await bot_app.bot.send_message(chat_id=CHAT_ID, text=f"🏁 Market Band - Final Summary\nTrades: {len(trades_today)} | Expected P&L: {total_pnl}")
            break

        # Sirf ek baar subah 9:30 pe Scan, fir har 30 min me check
        if not already_sent:
            ranked=[]
            for s in STOCKS:
                res = deep_check(s)
                if res:
                    score, price = res
                    ranked.append((s, score, price))
            ranked.sort(key=lambda x: x[1], reverse=True)
            best = ranked[:MAX_TRADES]

            if not best:
                await bot_app.bot.send_message(chat_id=CHAT_ID, text="❌ NO TRADE AAJ\nKoi stock 7/10 Score pass nahi kar paya.")
            else:
                msg = f"🔥 AAJ KE BEST {len(best)} TRADE | 1:3\nCapital 30k | Har Trade 10k\n\n"
                for i,(s,score,price) in enumerate(best,1):
                    entry=round(price,2)
                    sl=round(entry*(1-RISK_PCT),2)
                    target=round(entry*(1+REWARD_PCT),2)
                    qty=int(PER_TRADE_CAPITAL//entry)
                    loss=round((entry-sl)*qty); profit=round((target-entry)*qty)
                    total_pnl += profit
                    t_str = f"{i}. {s} - Entry {entry} | SL {sl} | Target {target} | Qty {qty}"
                    trades_today.append(t_str)
                    msg += f"*{i}. {s}* - Score {score}/10\nEntry: {entry} | Qty: {qty}\nSL: {sl} | Target: {target}\nLoss: ~{loss} | Profit: ~{profit}\n\n"
                msg += "⚠️ RULE: SL kate to dobara mat ghuso."
                await bot_app.bot.send_message(chat_id=CHAT_ID, text=msg)
            already_sent = True

        await asyncio.sleep(60)

    await bot_app.updater.stop()
    await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main_loop())
