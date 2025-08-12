# services/twelvedata_service.py
import requests
from datetime import datetime, timedelta
from config import TD_API_KEYS
import itertools
import io


class TwelveDataService:
    def __init__(self):
        self.api_keys = itertools.cycle(TD_API_KEYS)  # Rotate keys cyclically
        self.current_api_key = next(self.api_keys)
        self.last_rotation_time = datetime.now()

    def _rotate_api_key(self):
        """Rotate API key every 6 hours."""
        if datetime.now() - self.last_rotation_time > timedelta(hours=6):
            self._force_rotate_api_key()

    def _force_rotate_api_key(self):
        """Force rotation immediately."""
        self.current_api_key = next(self.api_keys)
        self.last_rotation_time = datetime.now()
        print(f"[TwelveData] Rotated API key to: {self.current_api_key}")

    def _request(self, endpoint: str, params: dict, retry: bool = True):
        """Internal request handler with error handling & auto key rotation."""
        self._rotate_api_key()  # Check time-based rotation
        params["apikey"] = self.current_api_key

        url = f"https://api.twelvedata.com/{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        # Handle API limit errors
        if "code" in data and data["code"] == 429:
            print(f"[TwelveData] Rate limit hit for key {self.current_api_key}")
            if retry:
                self._force_rotate_api_key()
                return self._request(endpoint, params, retry=False)

        if "message" in data and "run out of api credits" in data["message"].lower():
            print(f"[TwelveData] Daily limit reached for key {self.current_api_key}")
            if retry:
                self._force_rotate_api_key()
                return self._request(endpoint, params, retry=False)

        return data

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalize to TwelveData format for forex, stocks, and commodities."""
        s = symbol.strip().upper()

        # Already in correct format (has /)
        if "/" in s:
            return s

        # Forex pairs without slash, e.g., EURUSD -> EUR/USD
        if len(s) == 6 and s.isalpha():
            return f"{s[0:3]}/{s[3:6]}"

        # Stocks, commodities, indices — return as is
        return s

    def get_price(self, symbol: str):
        """Fetch real-time price."""
        normalized_symbol = self.normalize_symbol(symbol)
        data = self._request("price", {"symbol": normalized_symbol})

        if "price" in data:
            return float(data["price"])
        else:
            raise Exception(f"TwelveData API error: {data}")

    def get_ohlc(self, symbol: str, interval: str, outputsize: int = 200):
        """Fetch OHLC candlestick data."""
        normalized_symbol = self.normalize_symbol(symbol)
        data = self._request("time_series", {
            "symbol": normalized_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON"
        })

        if "values" in data:
            return list(reversed(data["values"]))  # Reverse so oldest first
        else:
            raise Exception(f"TwelveData API error: {data.get('message', 'Unknown error')}")
