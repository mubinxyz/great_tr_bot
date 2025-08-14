# utils/get_data.py

import requests
# import itertools
# from datetime import datetime, timedelta
import pandas as pd
import time
from utils.scrape_last_data import get_last_data
from utils.normalize_data import normalize_symbol, normalize_timeframe, normalize_ohlc  
import json

# # --- API Key Management ---
# _td_api_keys = itertools.cycle(TD_API_KEYS)
# _current_api_key = next(_td_api_keys)
# _last_rotation_time = datetime.now()


# def _rotate_api_key():
#     """Rotate API key every 6 hours."""
#     global _current_api_key, _last_rotation_time
#     if datetime.now() - _last_rotation_time > timedelta(hours=6):
#         _force_rotate_api_key()


# def _force_rotate_api_key():
#     """Force rotation immediately."""
#     global _current_api_key, _last_rotation_time
#     _current_api_key = next(_td_api_keys)
#     _last_rotation_time = datetime.now()
#     print(f"[TwelveData] Rotated API key to: {_current_api_key}")


def get_ohlc(symbol: str, timeframe: int = 15, from_date: int = None, to_date: int = time.time()) -> pd.DataFrame:
    """
    Get OHLC candles for a symbol.
    """
    norm_symbol = normalize_symbol(symbol)
    norm_timeframe = normalize_timeframe(timeframe)

    # --- 1. Try LiteFinance ---
    try:
        lite_finance_url = (
            f"https://my.litefinance.org/chart/get-history"
            f"?symbol={symbol}&resolution={norm_timeframe}&from={from_date}&to={to_date}"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://my.litefinance.org/",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = requests.get(lite_finance_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        ohlc_data = data.get("data", {})

        if ohlc_data:
            df = normalize_ohlc(ohlc_data)
            return df
    except Exception as e:
        print(f"[LiteFinance] OHLC error: {e}")


def get_price(symbol: str) -> dict | None:
    """
    Get the latest price of a symbol.
    1. Try scraping LiteFinance.
    2. If scraping fails, use TwelveData API.
    """
    norm_symbol = normalize_symbol(symbol)

    # --- 1. Try LiteFinance scrape ---
    try:
        result_raw = get_last_data(symbol)  # this is a string
        # parse it into a dict
        if isinstance(result_raw, str):
            result = json.loads(result_raw)
        else:
            result = result_raw

        price = result.get("price")
        bid = result.get("bid")
        ask = result.get("ask")
        if price is not None:
            return {
                "source": "litefinance scraped last data",
                "symbol": norm_symbol,
                "price": float(price),
                "bid": bid,
                "ask": ask
            }
        else:
            print(f"[LiteFinance] Script returned no price.")
    except Exception as e:
        print(f"[LiteFinance] Error: {e}")