# utils/get_data.py


import subprocess
import json
import requests
import itertools
from datetime import datetime, timedelta
from config import TD_API_KEYS
from utils.normalize_data import normalize_symbol, normalize_ohlc
import pandas as pd

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

    
    def get_ohlc(self, symbol: str, timeframe: int, date_start: int = 1, outputsize: int = 200) -> pd.DataFrame:
        """
        Get OHLC candles for a symbol.

        Args:
            symbol (str): Trading symbol, e.g. 'BTCUSD'
            timeframe (int): Candle period in minutes (LiteFinance expects minutes).
            date_start (int): Month number to start from for LiteFinance (1 = January).
            outputsize (int): Number of candles to return (both for trimming LiteFinance results
                            and for passing to TwelveData fallback).

        Returns:
            pandas.DataFrame with columns ['datetime', 'open', 'high', 'low', 'close'] sorted ascending.
            If both sources fail returns an empty DataFrame.
        """
        from utils.normalize_data import normalize_symbol, normalize_ohlc  # local import to avoid cycles
        norm_symbol = normalize_symbol(symbol)

        # --- 1. Try LiteFinance URL  ---
        try:
            lite_url = (
                f"https://www.litefinance.org/trading/trading-instruments/chart/"
                f"?symbol={norm_symbol}&period={timeframe}&date_start={date_start}"
            )
            resp = requests.get(lite_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "success" and "content" in data and data["content"]:
                # data["content"] is a list of lists: [timestamp_ms, open, high, low, close]
                df = normalize_ohlc(data["content"])  # returns chronological df with datetime column
                # Keep only the latest `outputsize` rows if requested
                if outputsize is not None and outputsize > 0:
                    df = df.tail(outputsize).reset_index(drop=True)
                return df
        except Exception as e:
            # Log but continue to fallback
            print(f"[LiteFinance] OHLC error: {e}")

        # --- 2. Fall back to TwelveData ---
        try:
            self._rotate_api_key()
            # TwelveData accepts intervals like '1min', '5min', '15min', '60min' etc.
            # We'll use '<timeframe>min' which is compatible for common minute-based intervals.
            td_interval = f"{timeframe}min"
            td_url = (
                f"https://api.twelvedata.com/time_series?"
                f"symbol={norm_symbol}&interval={td_interval}&outputsize={outputsize}&apikey={self.current_api_key}"
            )
            resp = requests.get(td_url, timeout=15)
            resp.raise_for_status()
            td_data = resp.json()

            if "values" in td_data and td_data["values"]:
                df = pd.DataFrame(td_data["values"])
                # ensure numeric and datetime types
                for col in ["open", "high", "low", "close"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                df.sort_values("datetime", inplace=True)
                df.reset_index(drop=True, inplace=True)
                if outputsize is not None and outputsize > 0:
                    df = df.tail(outputsize).reset_index(drop=True)
                return df
        except Exception as e:
            print(f"[TwelveData] OHLC error: {e}")

        # Both sources failed
        return pd.DataFrame() 
    
    
    
    def get_price(self, symbol: str):
        """
        Get the latest price of a symbol.
        1. Try scraping LiteFinance (scrape_last_data.py).
        2. If scraping fails, use TwelveData API.
        """
        norm_symbol = normalize_symbol(symbol)

        # --- 1. Try scraping LiteFinance ---
        try:
            result = subprocess.run(
                ["python", "utils/scrape_last_data.py", norm_symbol],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                if "price" in data:
                    return {
                        "source": "litefinance",
                        "symbol": norm_symbol,
                        "price": float(data["price"]),
                        "bid": float(data["bid"]),
                        "ask": float(data["ask"])
                    }
            else:
                print(f"[LiteFinance] Script failed: {result.stderr}")
        except Exception as e:
            print(f"[LiteFinance] Error: {e}")

        # --- 2. Fall back to TwelveData ---
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