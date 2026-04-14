import requests

WEBHOOK_URL = "https://wtalerts.com/bot/custom"

r = requests.post(WEBHOOK_URL, json={
    "code": "ENTER-LONG_Bybit_ETHUSDT_ETH-USDT_15M_8b9f1a73de3fa902b45b458e",
    "amountPerTrade": 20,
    "amountPerTradeType": "quote",
    "orderType": "market",
    "stopLoss": {
        "priceDeviation": 0.8
    }
})

print(r.status_code, r.text)