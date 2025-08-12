# services/strategy_twelvedata_service.py

import requests
from datetime import datetime, timedelta
import itertools
import time
from typing import Optional
from config import TD_STRATEGY_API_KEYS


class StrategyTwelveDataService:
    """
    Minimal wrapper around TwelveData time_series endpoint for backtesting.
    Rotates through provided API keys to reduce rate-limit hits.
    """

    BASE = "https://api.twelvedata.com/"

    def __init__(self):
        if not TD_STRATEGY_API_KEYS:
            raise ValueError("No TwelveData API keys provided for strategy service (TD_STRATEGY_API_KEYS is empty).")
        self.api_keys = itertools.cycle(TD_STRATEGY_API_KEYS)
        self.current_api_key = next(self.api_keys)

    def _next_key(self):
        # rotate to next key and return it
        self.current_api_key = next(self.api_keys)
        return self.current_api_key

    def _request(self, endpoint: str, params: dict, max_retries: int = 3):
        url = self.BASE.rstrip("/") + "/" + endpoint.lstrip("/")
        params = dict(params)  # copy
        params.setdefault("apikey", self.current_api_key)

        for attempt in range(max_retries):
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # TwelveData may return error object with "status": "error" or "message" keys
                if isinstance(data, dict) and data.get("status") == "error":
                    # if it's a rate-limited error, rotate key and retry
                    msg = data.get("message", "")
                    if "rate limit" in msg.lower() or "quota" in msg.lower():
                        # rotate key and retry
                        params["apikey"] = self._next_key()
                        time.sleep(0.5)
                        continue
                    raise RuntimeError(f"TwelveData error: {msg}")
                return data
            elif resp.status_code in (429,):
                params["apikey"] = self._next_key()
                time.sleep(0.5)
                continue
            else:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("status") == "error":
                        raise RuntimeError(f"TwelveData error: {data.get('message')}")
                except Exception:
                    pass
                resp.raise_for_status()

        raise RuntimeError("Failed to fetch data from TwelveData after retries.")

    def get_ohlc(self, symbol: str, interval: str = "1h", outputsize: int = 500):
        """
        Fetch OHLC candlestick data tailored for backtesting.
        Returns list of dicts with keys: datetime, open, high, low, close, volume.
        interval examples: 1min, 5min, 15min, 30min, 1h, 4h, 1day
        """
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be a non-empty string")

        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON",
        }

        data = self._request("time_series", params)

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected response from TwelveData API.")

        values = data.get("values")
        if not values:
            if "status" in data and data.get("status") == "error":
                raise RuntimeError(f"TwelveData API error: {data.get('message')}")
            raise RuntimeError(f"No OHLC values returned for {symbol} with interval {interval}.")

        # API returns newest-first; we want oldest-first for backtesting
        return list(reversed(values))
