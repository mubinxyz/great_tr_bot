# utils/get_data.py

import requests
import itertools
from datetime import datetime, timedelta
from config import TD_API_KEYS
import pandas as pd
import time
from utils.scrape_last_data import fetch_last_price_json
from utils.normalize_data import normalize_symbol, normalize_timeframe, normalize_ohlc  # ✅ import here


class DataService:
    def __init__(self):
        self.td_api_keys = itertools.cycle(TD_API_KEYS)
        self.current_api_key = next(self.td_api_keys)
        self.last_rotation_time = datetime.now()

    def _rotate_api_key(self):
        """Rotate API key every 6 hours."""
        if datetime.now() - self.last_rotation_time > timedelta(hours=6):
            self._force_rotate_api_key()

    def _force_rotate_api_key(self):
        """Force rotation immediately."""
        self.current_api_key = next(self.td_api_keys)
        self.last_rotation_time = datetime.now()
        print(f"[TwelveData] Rotated API key to: {self.current_api_key}")

    def get_ohlc(self, symbol: str, timeframe: int = 15, from_date: int = None, to_date: int = time.time()) -> pd.DataFrame:
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

        # --- 2. Fallback to TwelveData ---
        try:
            self._rotate_api_key()
            td_interval = f"{timeframe}min"
            td_url = (
                f"https://api.twelvedata.com/time_series?"
                f"symbol={norm_symbol}&interval={td_interval}&apikey={self.current_api_key}"
            )
            resp = requests.get(td_url, timeout=15)
            resp.raise_for_status()
            td_data = resp.json()

            if "values" in td_data and td_data["values"]:
                df = pd.DataFrame(td_data["values"])
                for col in ["open", "high", "low", "close"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                df.sort_values("datetime", inplace=True)
                df.reset_index(drop=True, inplace=True)
                return df
        except Exception as e:
            print(f"[TwelveData] OHLC error: {e}")

        return pd.DataFrame()

    def get_price(self, symbol: str) -> int:
        """
        Get the latest price of a symbol.
        1. Try scraping LiteFinance.
        2. If scraping fails, use TwelveData API.
        """
        norm_symbol = normalize_symbol(symbol)

        # --- 1. Try LiteFinance scrape ---
        try:
            result = fetch_last_price_json(symbol).json()
            price = result.get("price")
            if price:
                return {
                    "source": "litefinance scraped last data",
                    "symbol": norm_symbol,
                    "price": float(price)
                }
            else:
                print(f"[LiteFinance] Script returned no price.")
        except Exception as e:
            print(f"[LiteFinance] Error: {e}")

        # --- 2. Fallback to TwelveData ---
        try:
            self._rotate_api_key()
            td_url = f"https://api.twelvedata.com/price?symbol={norm_symbol}&apikey={self.current_api_key}"
            resp = requests.get(td_url, timeout=10)
            resp.raise_for_status()
            td_data = resp.json()

            if "price" in td_data:
                return {
                    "source": "twelvedata",
                    "symbol": norm_symbol,
                    "price": float(td_data["price"])
                }
        except Exception as e:
            print(f"[TwelveData] Error: {e}")

        return None
