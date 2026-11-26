import os, requests, datetime, time
import pandas as pd
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram Fail: {e}")

def get_candles(instrument_key):
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}
        to_date = datetime.date.today().strftime("%Y-%m-%d")
        from_date = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/5minute/{to_date}/{from_date}"
        r = requests.get(url, headers=headers, timeout=20)
        data = r.json().get("data", {}).get("candles", [])
        if not data:
            return None
        df = pd.DataFrame(data, columns=["time","open","high","low","close","volume","oi"])
        df = df.sort_values("time").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Candle Error: {e}")
        return None

def analyze(df):
    if df is None or len(df) < 20:
        return None
    df = df.fillna(method="ffill").fillna(0)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (typical * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, 1)
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    curr_vol = df["volume"].iloc[-1]
    rvol = curr_vol / avg_vol if avg_vol and avg_vol > 0 else 0
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss.replace(0, 1)
    rsi = 100 - (100 / (1 + rs))
    curr_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    price = df["close"].iloc[-1]
    vwap = df["vwap"].iloc[-1]
    return {"price": price, "vwap": round(vwap,2), "rvol": round(rvol,2), "rsi": round(curr_rsi,1), "above_vwap": price > vwap}

def main():
    try:
        if datetime.datetime.now().weekday() >= 5:
            print("Weekend Skip")
            return
        stocks = {
            "NIFTY 50": "NSE_INDEX|Nifty 50",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            "RELIANCE": "NSE_EQ|INE002A01018",
            "TCS": "NSE_EQ|INE467B01029",
            "INFY": "NSE_EQ|INE009A01021",
        }
        results = []
        for name, key in stocks.items():
            df = get_candles(key)
            ind = analyze(df)
            if ind:
                score = 0
                if ind["above_vwap"]: score += 30
                if ind["rvol"] > 1.5: score += 30
                elif ind["rvol"] > 1.0: score += 15
                if 50 < ind["rsi"] < 70: score += 20
                if ind["rvol"] > 1.0 and ind["above_vwap"]: score += 20
                results.append((name, score, ind))
            time.sleep(1)

        if not results:
            send_telegram("⚠️ <b>BOT ALERT:</b> Upstox se Data nahi aaya. Access Token Expire to nahi ho gaya? Check kar.")
            return

        results.sort(key=lambda x: x[1], reverse=True)
        top_name, top_score, top_ind = results[0]

        if top_score >= 70:
            sl = round(top_ind["price"] * 0.997, 2)
            target = round(top_ind["price"] * 1.006, 2)
            msg = f"🚀 <b>SIGNAL - {top_name}</b>\n💰 Price: {top_ind['price']}\n📊 Score: {top_score}/100\n🎯 Target: {target}\n🛑 SL: {sl}\n📈 VWAP: {top_ind['vwap']} | RVOL: {top_ind['rvol']}x | RSI: {top_ind['rsi']}\nSource: Upstox Live"
            send_telegram(msg)
        else:
            msg = f"📊 <b>SCAN COMPLETE - No Trade</b>\nTop: {top_name} - Score {top_score}/100\nPrice: {top_ind['price']} | VWAP: {top_ind['vwap']} | RVOL: {top_ind['rvol']}x | RSI: {top_ind['rsi']}\nBot Sahi Chal Raha Hai."
            send_telegram(msg)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        send_telegram(f"❌ <b>BOT CRASH</b>\nError: {str(e)[:400]}")

if __name__ == "__main__":
    main()
