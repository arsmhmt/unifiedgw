import requests
from app.models.currency import CurrencyRate
from ..utils.timezone import now_eest
from app.extensions import db
from datetime import datetime

def update_btc_rates():
    url = "https://api.coingecko.com/api/v3/simple/price"
    symbols = ["usd", "eth", "usdt", "bnb", "trx"]
    params = {
        "ids": ",".join(symbols),
        "vs_currencies": "btc"
    }
    response = requests.get(url, params=params)
    data = response.json()

    for symbol in symbols:
        btc_rate = data.get(symbol, {}).get("btc")
        if btc_rate:
            existing = CurrencyRate.query.get(symbol.upper())
            if existing:
                existing.btc_rate = btc_rate
                existing.updated_at = now_eest()
            else:
                db.session.add(CurrencyRate(
                    currency=symbol.upper(),
                    btc_rate=btc_rate
                ))
    db.session.commit()
