import os, requests, yfinance as yf, pandas as pd, numpy as np
from datetime import datetime
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CAPITAL = 100000

def send(msg):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def clean(df):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df

def indi(df):
    c=df['Close']; df['EMA9']=c.ewm(9).mean(); df['EMA21']=c.ewm(21).mean(); df['EMA50']=c.ewm(50).mean()
    d=c.diff(); g=d.where(d>0,0).rolling(14).mean(); l=-d.where(d<0,0).rolling(14).mean()
    df['RSI']=100-(100/(1+g/l))
    df['MACD']=c.ewm(12).mean()-c.ewm(26).mean(); df['SIG']=df['MACD'].ewm(9).mean()
    df['ATR']=(df['High']-df['Low']).rolling(14).mean()
    up=df['High'].diff(); dn=-df['Low'].diff()
    pdm=np.where((up>dn)&(up>0),up,0); mdm=np.where((dn>up)&(dn>0),dn,0)
    atr=(df['High']-df['Low']).rolling(14).mean()
    pdi=100*(pd.Series(pdm,index=df.index).rolling(14).mean()/atr); mdi=100*(pd.Series(mdm,index=df.index).rolling(14).mean()/atr)
    df['ADX']=(100*abs(pdi-mdi)/(pdi+mdi)).rolling(14).mean()
    df['RVOL']=df['Volume']/df['Volume'].rolling(20).mean()
    df['VWAP']=(c*df['Volume']).rolling(20).sum()/df['Volume'].rolling(20).sum()
    return df

def backtest_fast(df):
    buy = (df['Close']>df['VWAP']) & (df['ADX']>20) & (df['EMA9']>df['EMA21']) & (df['RSI']>45) & (df['RSI']<65) & (df['MACD']>df['SIG'])
    sell = (df['Close']<df['VWAP']) & (df['ADX']>20) & (df['EMA9']<df['EMA21']) & (df['RSI']>35) & (df['RSI']<55) & (df['MACD']<df['SIG'])
    nxt = df['Close'].shift(-1)
    buy_win = ((buy) & (nxt > df['Close'])).sum()
    sell_win = ((sell) & (nxt < df['Close'])).sum()
    total = int(buy.sum() + sell.sum()); wins = int(buy_win + sell_win)
    acc = round(wins/total*100,1) if total else 0
    return total, wins, acc

def score(last, vwap, rsi, adx, rvol, vix, pdh, acc):
    s=0; rs=[]
    def add(c,t):
        nonlocal s
        if c: s+=1; rs.append(f"✅ {t}")
        else: rs.append(f"❌ {t}")
    p=float(last['Close'])
    add(p>vwap, f"VWAP {vwap} Upar"); add(adx>20, f"ADX {adx}>20"); add(45<rsi<65, f"RSI {rsi}"); add(float(last['MACD'])>float(last['SIG']), "MACD Bullish"); add(float(last['EMA9'])>float(last['EMA21']), "EMA9>21"); add(p>float(last['EMA50']), "EMA50 Upar"); add(rvol>0.8, f"RVOL {rvol}"); add(vix<20, f"VIX {vix}"); add(p>pdh, f"PDH {pdh} Break"); add(acc>=55, f"Backtest {acc}%")
    return s, rs

def main():
    try:
        d1=clean(yf.download("^NSEI", period="2y", interval="1d", progress=False, auto_adjust=True))
        di=clean(yf.download("^NSEI", period="60d", interval="15m", progress=False, auto_adjust=True))
        vx=clean(yf.download("^INDIAVIX", period="5d", interval="1d", progress=False, auto_adjust=True))
        d1=indi(d1); di=indi(di)
        ld=d1.iloc[-1]; pdh=d1.iloc[-2]; li=di.iloc[-1]
        t1,w1,a1=backtest_fast(d1); t2,w2,a2=backtest_fast(di)
        vix=round(float(vx.iloc[-1]['Close']),2); price=round(float(ld['Close']),2)
        atr_d=round(float(ld['ATR']),2); atr_i=round(float(li['ATR']),2)
        today=datetime.now(); is_exp=today.weekday()==1; atm=round(price/50)*50
        s_i,r_i=score(li, round(float(li['VWAP']),2), round(float(li['RSI']),1), round(float(li['ADX']),1), round(float(li['RVOL']),2), vix, round(float(pdh['High']),2), a2)
        s_s,r_s=score(ld, round(float(ld['VWAP']),2), round(float(ld['RSI']),1), round(float(ld['ADX']),1), round(float(ld['RVOL']),2), vix, round(float(pdh['High']),2), a1)
        is_fixed=(today.hour==3 and 10<=today.minute<=25)
        is_solid=(s_i>=7 or s_i<=3 or s_s>=7 or s_s<=3)
        if not is_fixed and not is_solid:
            print(f"Silent Intra {s_i} Swing {s_s}"); return
        fut=f"🟢 FUTURE BUY {price} SL {round(price-atr_i,2)} T1 {round(price+atr_i,2)} T2 {round(price+atr_i*2,2)}" if s_i>=7 else f"🔴 FUTURE SELL {price} SL {round(price+atr_i,2)} T1 {round(price-atr_i,2)}" if s_i<=3 else f"🟡 FUTURE NO TRADE {s_i}/10"
        sw=f"🟢 SWING BUY {price} SL {round(price-atr_d,2)} T1 {round(price+atr_d,2)} T2 {round(price+atr_d*2,2)}" if s_s>=7 else f"🔴 SWING SELL {price} SL {round(price+atr_d,2)}" if s_s<=3 else f"🟡 SWING NO TRADE {s_s}/10"
        if vix>=20: opt=f"⛔ OPTION MAT LO - VIX {vix} HIGH"
        elif is_exp: opt="⚠️ EXPIRY HAI - 1 Lot Only"
        elif s_i>=7: opt=f"🟢 OPTION BUY {atm} CE ATM - Score {s_i}/10"
        elif s_i<=3: opt=f"🔴 OPTION BUY {atm} PE ATM - Score {s_i}/10"
        else: opt=f"🟡 OPTION NO TRADE {s_i}/10"
        msg=f"""✅ <b>MyAlgoBot - LIGHT + ACCURATE</b>\n📅 {today.strftime('%d %b %A %I:%M %p')}\n📊 <b>NIFTY {price} | VIX {vix}</b> {'⚠️ EXPIRY' if is_exp else ''}\n<b>1️⃣ FUTURE</b>\n{fut}\n<b>2️⃣ SWING</b>\n{sw}\n<b>3️⃣ OPTION</b>\n{opt}\n<b>LOGIC Intra:</b>\n{chr(10).join(r_i)}\n<b>LOGIC Swing:</b>\n{chr(10).join(r_s)}\n<b>💰 RISK:</b> 1 Trade ₹1000 | Daily ₹3000\n<b>🧪 BACKTEST 2 SAAL:</b> Daily {a1}% ({w1}/{t1}) | Intra {a2}% ({w2}/{t2})\n"""
        send(msg)
    except Exception as e: send(f"❌ Error: {str(e)}")
if __name__=="__main__": main()
