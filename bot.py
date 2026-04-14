import ccxt
import pandas as pd
import requests
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, UTC
print(f"[{datetime.now(UTC)}] {msg}")
import requests

try:
    ip = requests.get("https://api.ipify.org").text
    print("MY PUBLIC IP:", ip)
except Exception as e:
    print("IP ERROR:", e)


# ======================
# FAKE SERVER (RENDER)
# ======================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# ======================
# KONFIG
# ======================

SYMBOL = "ETH/USDT"
TIMEFRAME = "15m"

WEBHOOK_URL = "https://wtalerts.com/bot/custom"

ENTER_LONG = "ENTER-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
ENTER_SHORT = "ENTER-SHORT_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"

POSITION_SIZE = 20

exchange = ccxt.binance()

# ======================
# LOG
# ======================

def log(msg):
    print(f"[{datetime.utcnow()}] {msg}")

# ======================
# DATA
# ======================

def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=200)
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
# STRATEGIA
# ======================

def get_signal(df):
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])

    last = df.iloc[-1]

    body = abs(last["close"] - last["open"])
    candle = last["high"] - last["low"]

    if candle == 0 or body < candle * 0.5:
        return None

    recent_high = df["high"].rolling(20).max().iloc[-2]
    recent_low = df["low"].rolling(20).min().iloc[-2]

    if last["ema50"] > last["ema200"] and last["rsi"] > 60 and last["close"] > recent_high:
        return "LONG"

    if last["ema50"] < last["ema200"] and last["rsi"] < 40 and last["close"] < recent_low:
        return "SHORT"

    return None

# ======================
# SEND
# ======================

def send(msg):
    payload = {"code": msg}

    if "ENTER" in msg:
        payload.update({
            "amountPerTrade": POSITION_SIZE,
            "amountPerTradeType": "quote",
            "orderType": "market",
            "stopLoss": {
                "priceDeviation": 0.8
            }
        })

    try:
        r = requests.post(WEBHOOK_URL, json=payload)
        log(f"Sent: {payload} | {r.status_code} | {r.text}")
    except Exception as e:
        log(f"Send error: {e}")

# ======================
# BOT LOOP
# ======================

def run_bot():
    log("BOT STARTED")

    while True:
        try:
            df = get_data()
            signal = get_signal(df)

            if signal == "LONG":
                send(ENTER_LONG)

            elif signal == "SHORT":
                send(ENTER_SHORT)

            else:
                log("No signal")

            time.sleep(60 * 15)

        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(60)

# ======================
# START BOT
# ======================

run_bot()
