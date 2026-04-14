import ccxt
import pandas as pd
import requests
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, UTC

# ======================
# SERVER (RENDER)
# ======================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

# ======================
# LOG
# ======================

def log(msg):
    print(f"[{datetime.now(UTC)}] {msg}", flush=True)

# ======================
# IP CHECK
# ======================

def print_ip():
    try:
        ip = requests.get("https://api.ipify.org").text
        log(f"MY PUBLIC IP: {ip}")
    except Exception as e:
        log(f"IP ERROR: {e}")

# ======================
# CONFIG
# ======================

SYMBOL = "ETH/USDT:USDT"
TIMEFRAME = "15m"

WEBHOOK_URL = "https://wtalerts.com/bot/custom"

ENTER_LONG = "ENTER-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
ENTER_SHORT = "ENTER-SHORT_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
EXIT_LONG = "EXIT-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"
EXIT_SHORT = "EXIT-SHORT_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e"

POSITION_SIZE = 20
TRAILING_STOP = 1.0  # %

exchange = ccxt.bybit({"enableRateLimit": True})

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
# STRATEGY
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
# STATE
# ======================

position = None
highest_price = 0
lowest_price = 999999

# ======================
# BOT LOOP
# ======================

def run_bot():
    global position, highest_price, lowest_price

    log("BOT STARTED")
    print_ip()

    while True:
        try:
            df = get_data()
            price = df.iloc[-1]["close"]
            signal = get_signal(df)

            # 🔁 IP CHECK co 30 min
            if int(time.time()) % 1800 < 60:
                print_ip()

            # ENTRY
            if signal == "LONG" and position is None:
                send(ENTER_LONG)
                position = "LONG"
                highest_price = price

            elif signal == "SHORT" and position is None:
                send(ENTER_SHORT)
                position = "SHORT"
                lowest_price = price

            # TRAILING LONG
            elif position == "LONG":
                if price > highest_price:
                    highest_price = price

                drawdown = (highest_price - price) / highest_price * 100

                if drawdown >= TRAILING_STOP:
                    log("EXIT LONG (trailing)")
                    send(EXIT_LONG)
                    position = None

            # TRAILING SHORT
            elif position == "SHORT":
                if price < lowest_price:
                    lowest_price = price

                drawdown = (price - lowest_price) / lowest_price * 100

                if drawdown >= TRAILING_STOP:
                    log("EXIT SHORT (trailing)")
                    send(EXIT_SHORT)
                    position = None

            else:
                log("No signal")

            time.sleep(60 * 15)

        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(60)

# ======================
# START
# ======================

threading.Thread(target=run_server, daemon=True).start()
threading.Thread(target=run_bot, daemon=True).start()

while True:
    time.sleep(60)
