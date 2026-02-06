import ccxt
import pandas as pd
import matplotlib.pyplot as plt
import requests
import io
import time

# ================== AYARLAR ==================
TELEGRAM_TOKEN = "8312596185:AAGSfuwAJXUiHO58WIE2jPMe4EAtQnjsgvo"
CHAT_ID = "1431650503"

TIMEFRAMES = ["4h", "1d"]
LIMIT = 200
EMA_FAST = 50
EMA_SLOW = 200
MIN_SCORE = 70

exchange = ccxt.mexc()

# ================== TELEGRAM ==================
def send_telegram(text, image):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {"photo": image}
    data = {"chat_id": CHAT_ID, "caption": text}
    requests.post(url, files=files, data=data)

# ================== İNDİKATÖRLER ==================
def ema(series, period):
    return series.ewm(span=period).mean()

def volume_ok(df):
    return df["volume"].iloc[-1] > df["volume"].rolling(20).mean().iloc[-1]

def trend_ok(df):
    return df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1]

# ================== PATTERN ==================
def continuation(df):
    return df["close"].iloc[-1] > df["high"].rolling(20).max().iloc[-2]

def reversal(df):
    l = df["low"].values
    return l[-3] > l[-2] < l[-1]

# ================== LIQUIDITY ==================
def detect_liquidity(df, lookback=20):
    high = df["high"].rolling(lookback).max().iloc[-2]
    low = df["low"].rolling(lookback).min().iloc[-2]
    last = df.iloc[-1]

    if last["high"] > high and last["close"] < high:
        return "high", last["high"], last["low"]
    if last["low"] < low and last["close"] > low:
        return "low", last["high"], last["low"]
    return None, None, None

# ================== WYCKOFF ==================
def wyckoff(df, bars=40):
    r = df.iloc[-bars:]
    last = df.iloc[-1]
    if last["low"] < r["low"].min() and last["close"] > r["low"].min():
        return True
    if last["high"] > r["high"].max() and last["close"] < r["high"].max():
        return True
    return False

# ================== ENTRY ZONE ==================
def entry_zone(liq_type, high, low):
    if liq_type == "low":
        z_low = low + (high - low) * 0.50
        z_high = low + (high - low) * 0.70
    elif liq_type == "high":
        z_low = low + (high - low) * 0.30
        z_high = low + (high - low) * 0.50
    else:
        return None, None
    return z_low, z_high

# ================== SKOR ==================
def score_calc(trend, vol, cont, rev, liq, wyck):
    score = 0
    if trend: score += 20
    if vol: score += 20
    if cont or rev: score += 15
    if liq: score += 20
    if wyck: score += 25
    return score

# ================== GRAFİK ==================
def plot_chart(df, symbol, tf, liq_type, liq_high, liq_low, z_low, z_high):
    plt.figure(figsize=(9,4))
    plt.plot(df["close"], label="Close")
    plt.plot(df["ema_fast"], label="EMA 50")
    plt.plot(df["ema_slow"], label="EMA 200")

    if liq_type == "high":
        plt.axhline(liq_high, color="red", linestyle="--", label="Liquidity High")
    if liq_type == "low":
        plt.axhline(liq_low, color="green", linestyle="--", label="Liquidity Low")

    if z_low and z_high:
        plt.axhspan(z_low, z_high, color="orange", alpha=0.3, label="Entry Zone")

    plt.title(f"{symbol} {tf}")
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf

# ================== SCAN ==================
def scan_symbol(symbol):
    for tf in TIMEFRAMES:
        try:
            data = exchange.fetch_ohlcv(symbol, tf, limit=LIMIT)
            df = pd.DataFrame(data, columns=["t","open","high","low","close","volume"])
            df["ema_fast"] = ema(df["close"], EMA_FAST)
            df["ema_slow"] = ema(df["close"], EMA_SLOW)

            trend = trend_ok(df)
            vol = volume_ok(df)
            cont = continuation(df)
            rev = reversal(df)

            liq_type, liq_high, liq_low = detect_liquidity(df)
            wyck = wyckoff(df)

            z_low, z_high = entry_zone(liq_type, liq_high, liq_low)

            score = score_calc(trend, vol, cont, rev, liq_type, wyck)

            if score >= MIN_SCORE and liq_type:
                chart = plot_chart(df, symbol, tf, liq_type, liq_high, liq_low, z_low, z_high)
                msg = f"""
{symbol}
TF: {tf}

🧠 Setup Skoru: {score}/100
💧 Liquidity Sweep: {liq_type.upper()}
📦 Entry Zone: Var
📈 Trend: {"Bullish" if trend else "Bearish"}

➡️ Likidite sonrası manuel entry alanı
"""
                send_telegram(msg, chart)

        except:
            continue

# ================== MAIN ==================
def run():
    markets = exchange.load_markets()
    symbols = [s for s in markets if s.endswith("/USDT")]

    for s in symbols:
        scan_symbol(s)
        time.sleep(1)

if __name__ == "__main__":
    run()
