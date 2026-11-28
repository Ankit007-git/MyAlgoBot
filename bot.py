import os, requests, datetime, time
import pandas as pd
import pyotp

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- UPSTOX AUTO TOKEN - 6 Naye Variables ---
UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
UPSTOX_USER_ID = os.getenv("UPSTOX_USER_ID")
UPSTOX_PIN = os.getenv("UPSTOX_PIN")
UPSTOX_TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram Fail: {e}")

def get_auto_token():
    # Auto Token banane ki koshish, Fail hua to Purana Token hi chalega
    try:
        if not UPSTOX_TOTP_SECRET:
            print("TOTP Secret nahi mila, Purana Token use kar raha hu")
            return None
        otp = pyotp.TOTP(UPSTOX_TOTP_SECRET).now()
        print(f"Auto Token Try - TOTP: {otp} - User: {UPSTOX_USER_ID}")
        # Upstox ka Auto Login yaha hoga
        # Agar Captcha aaya to ye Fail hoga aur neeche Purana Token chalega
        return None
    except Exception as e:
        print(f"Auto Token Fail: {e}")
        return None

# Pehle Auto try karo
_new_token = get_auto_token()
if _new_token:
    ACCESS_TOKEN = _new_token
    print("Naya Auto Token mil gaya ✅")
else:
    print("Purana UPSTOX_ACCESS_TOKEN se chal raha hu")

def get_candles(instrument_key):
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}
        to_date = datetime.date.today().strftime("%Y-%m-%d")
        from_date = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/5minute/{to_date}/{from_date}"
        r = requests.get(url, headers=headers, timeout=20)
        data = r.json().get("data", {}).get("candles", [])
        if not data:
            print(f"No Data {instrument_key}: {r.text[:200]}")
            return None
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "oi"])
        df = df.sort_values("time")
        return df
    except Exception as e:
        print(f"Candle Fail {instrument_key}: {e}")
        return None

def analyze(df):
    if df is None or len(df) < 20:
        return None
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema21"] = df["close"].ewm(span=21).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    # Simple Logic - EMA Cross
    if prev["ema9"] < prev["ema21"] and last["ema9"] > last["ema21"]:
        return f"🟢 BUY Signal - Close: {last['close']} | EMA9: {round(last['ema9'],2)} > EMA21: {round(last['ema21'],2)}"
    if prev["ema9"] > prev["ema21"] and last["ema9"] < last["ema21"]:
        return f"🔴 SELL Signal - Close: {last['close']} | EMA9: {round(last['ema9'],2)} < EMA21: {round(last['ema21'],2)}"
    return None

# --- MAIN SCAN ---
NIFTY = "NSE_INDEX|Nifty 50"

print(f"Bot Start: {datetime.datetime.now()}")
df = get_candles(NIFTY)
signal = analyze(df)

if signal:
    msg = f"<b>📊 MyAlgoBot - NIFTY Signal</b>\n\n{signal}\nTime: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"
    send_telegram(msg)
    print("Signal bheja ✅")
else:
    if df is not None:
        last_close = df.iloc[-1]["close"]
        msg = f"✅ <b>MyAlgoBot - LIVE Check</b>\nNIFTY: {last_close}\nTime: {datetime.datetime.now().strftime('%H:%M')}\nStatus: Scan chal raha hai, abhi koi Strong Signal nahi."
        send_telegram(msg)
        print("Live Check bheja ✅")
    else:
        send_telegram("⚠️ <b>MyAlgoBot</b>\nUpstox se Data nahi aaya. Token Expire ho sakta hai, GitHub Secrets me UPSTOX_ACCESS_TOKEN check karo.")
        print("Data Fail")