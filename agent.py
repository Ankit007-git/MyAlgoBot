import os, requests, yfinance as yf, pandas as pd, numpy as np
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_indicators(df):
    df = df.copy()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    e12 = df['Close'].ewm(span=12).mean()
    e26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = e12 - e26
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['BB_Mid'] = df['Close'].rolling(20).mean()
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df

def backtest(df):
    wins = 0
    total = 0
    total_profit_points = 0
    for i in range(30, len(df)-1):
        row = df.iloc[i]
        buy_cond = row['Close'] > row['VWAP'] and row['EMA9'] > row['EMA21'] and 50 < row['RSI'] < 70 and row['MACD'] > row['MACD_Signal']
        sell_cond = row['Close'] < row['VWAP'] and row['EMA9'] < row['EMA21'] and 30 < row['RSI'] < 50 and row['MACD'] < row['MACD_Signal']
        if buy_cond or sell_cond:
            total += 1
            next_close = float(df.iloc[i+1]['Close'])
            curr = float(row['Close'])
            if buy_cond:
                profit = next_close - curr
                if profit > 0:
                    wins += 1
                total_profit_points += profit
            if sell_cond:
                profit = curr - next_close
                if profit > 0:
                    wins += 1
                total_profit_points += profit
    acc = (wins/total*100) if total>0 else 0
    return wins, total, round(acc,1), round(total_profit_points,1)

def main():
    try:
        df_daily = yf.download("^NSEI", period="2y", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        df_daily = get_indicators(df_daily)
        last = df_daily.iloc[-1]

        wins, total, acc, total_points = backtest(df_daily)

        price = round(float(last['Close']),2)
        vwap = round(float(last['VWAP']),2)
        rsi = round(float(last['RSI']),1)
        ema9 = round(float(last['EMA9']),2)
        atr = round(float(last['ATR']),2)
        macd_bull = float(last['MACD']) > float(last['MACD_Signal'])

        score = 0
        reasons = []
        if price > vwap:
            score+=1; reasons.append("Price VWAP ke Upar ✅")
        else:
            reasons.append("Price VWAP ke Neeche ❌")
        if ema9 > float(last['EMA21']):
            score+=1; reasons.append("EMA9 > EMA21 Trend UP ✅")
        else:
            reasons.append("EMA Trend DOWN ❌")
        if 50 < rsi < 68:
            score+=1; reasons.append(f"RSI {rsi} Healthy ✅")
        elif rsi >= 70:
            reasons.append(f"RSI {rsi} Overbought - Risk ⚠️")
        else:
            reasons.append(f"RSI {rsi} Weak ⚠️")
        if macd_bull:
            score+=1; reasons.append("MACD Bullish ✅")
        else:
            reasons.append("MACD Bearish ❌")

        if score >= 4 and acc >= 55:
            signal = f"🟢 <b>NIFTY BUY Signal</b>\nEntry: {price}\nSL: {round(price-atr,2)}\nTarget 1: {round(price+atr,2)}\nTarget 2: {round(price+atr*2,2)}"
            action = "BUY"
        elif score <= 1 and acc >= 55:
            signal = f"🔴 <b>NIFTY SELL Signal</b>\nEntry: {price}\nSL: {round(price+atr,2)}\nTarget 1: {round(price-atr,2)}\nTarget 2: {round(price-atr*2,2)}"
            action = "SELL"
        else:
            signal = f"🟡 <b>NO TRADE TODAY</b>\nMarket Confused Hai. Paisa Bachao."
            action = "NO_TRADE"

        log = f"{datetime.now().strftime('%Y-%m-%d %H:%M')},Price={price},Score={score},Acc={acc}%,Action={action}\n"
        with open("backtest_log.csv","a") as f:
            f.write(log)

        msg = f"""✅ <b>MyAlgoBot PRO Live</b>
📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}
📊 <b>NIFTY 50: {price}</b>

{signal}

<b>Deep Analysis:</b>
- VWAP: {vwap}
- RSI: {rsi}
- EMA9: {ema9}
- ATR: {atr}
- MACD: {'Bullish' if macd_bull else 'Bearish'}

<b>Reasons:</b>
{chr(10).join(['• '+r for r in reasons])}

<b>🧪 BACKTEST (Last 2 Years Historical):</b>
Total Trades: {total} | Win: {wins} | Accuracy: {acc}%
Total Profit Points: {total_points}

<i>Manual Trade Karo. SL ka Pakka Palan Karo.</i>
"""
        send(msg)
    except Exception as e:
        send(f"❌ Bot Error: {str(e)}")

if __name__ == "__main__":
    main()
