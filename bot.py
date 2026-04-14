import ccxt
import pandas as pd
import requests
import time
from datetime import datetime

# ======================
# KONFIG
# ======================

SYMBOL = "ETH/USDT"

WEBHOOK_URL = "https://wtalerts.com/bot/custom"

ENTER_LONG = "ENTER-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
ENTER_SHORT = "ENTER-SHORT_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
EXIT_LONG = "EXIT-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
EXIT_SHORT = "EXIT-SHORT_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"

POSITION_SIZE = 20

exchange = ccxt.binance()

# ======================
# DATA
# ======================

def get_data(tf):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=tf, limit=200)
    df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
    return df

# ======================
# INDICATORS
# ======================

def ema(series, p):
    return series.ewm(span=p).mean()

def rsi(series, p=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(p).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(p).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ======================
# SESSION FILTER
# ======================

def is_trading_time():
    hour = datetime.utcnow().hour

    # London + NY
    return 8 <= hour <= 20

# ======================
# STRATEGIA PRO
# ======================

def get_signal():
    df15 = get_data("15m")
    df1h = get_data("1h")

    # 15m
    df15["ema50"] = ema(df15["close"], 50)
    df15["ema200"] = ema(df15["close"], 200)
    df15["rsi"] = rsi(df15["close"])

    # 1H trend
    df1h["ema50"] = ema(df1h["close"], 50)
    df1h["ema200"] = ema(df1h["close"], 200)

    last15 = df15.iloc[-1]
    last1h = df1h.iloc[-1]

    # trend HTF
    uptrend_htf = last1h["ema50"] > last1h["ema200"]
    downtrend_htf = last1h["ema50"] < last1h["ema200"]

    # momentum candle
    body = abs(last15["close"] - last15["open"])
    candle = last15["high"] - last15["low"]

    if candle == 0 or body < candle * 0.5:
        return None

    # breakout
    recent_high = df15["high"].rolling(20).max().iloc[-2]
    recent_low = df15["low"].rolling(20).min().iloc[-2]

    # LONG
    if (
        uptrend_htf and
        last15["ema50"] > last15["ema200"] and
        last15["rsi"] > 60 and
        last15["close"] > recent_high
    ):
        return "LONG"

    # SHORT
    if (
        downtrend_htf and
        last15["ema50"] < last15["ema200"] and
        last15["rsi"] < 40 and
        last15["close"] < recent_low
    ):
        return "SHORT"

    return None

# ======================
# SEND
# ======================

def send(msg):
    payload = {
        "code": msg
    }

    if "ENTER" in msg:
        payload.update({
            "amountPerTrade": POSITION_SIZE,
            "amountPerTradeType": "quote",
            "orderType": "market",
            "stopLoss": {
                "priceDeviation": 0.8
            }
        })

    r = requests.post(WEBHOOK_URL, json=payload)

    print("Sent:", payload)
    print("Status:", r.status_code)
    print("Response:", r.text)

# ======================
# STATE
# ======================

position = None

# ======================
# LOOP
# ======================

while True:
    try:
        if not is_trading_time():
            print("Outside trading hours")
            time.sleep(60 * 15)
            continue

        signal = get_signal()

        if signal == "LONG" and position is None:
            send(ENTER_LONG)
            position = "LONG"

        elif signal == "SHORT" and position is None:
            send(ENTER_SHORT)
            position = "SHORT"

        else:
            print("No action | Position:", position)

        time.sleep(60 * 15)

    except Exception as e:
        print("Error:", e)
        time.sleep(60)


try:
    while True:
        # Twój kod
        time.sleep(60 * 15)

except KeyboardInterrupt:
    print("Bot stopped manually")