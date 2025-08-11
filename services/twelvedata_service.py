# services/twelvedata_service.py
import requests
from datetime import datetime, timedelta
from config import TD_API_KEYS
import itertools

class TwelveDataService:
    def __init__(self):
        self.api_keys = itertools.cycle(TD_API_KEYS)  # Rotate keys
        self.current_api_key = next(self.api_keys)
        self.last_rotation_time = datetime.now()

    def _rotate_api_key(self, force=False):
        """Rotate the API key every 6 hours or if forced."""
        if force or (datetime.now() - self.last_rotation_time > timedelta(hours=6)):
            old_key = self.current_api_key
            self.current_api_key = next(self.api_keys)
            self.last_rotation_time = datetime.now()
            print(f"[TwelveData] Rotated API key: {old_key[:4]}**** -> {self.current_api_key[:4]}****")

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        cleaned = symbol.replace("/", "").upper()
        if len(cleaned) == 6:
            return f"{cleaned[0:3]}/{cleaned[3:6]}"
        else:
            raise ValueError(f"Invalid currency pair format: {symbol}")

    def get_price(self, symbol: str):
        self._rotate_api_key()
        normalized_symbol = self.normalize_symbol(symbol)

        url = "https://api.twelvedata.com/price"
        params = {"symbol": normalized_symbol, "apikey": self.current_api_key}

        response = requests.get(url, params=params)
        data = response.json()

        # Handle API limit error
        if "code" in data and data["code"] == 429:
            print("[TwelveData] Rate limit hit, rotating API key...")
            self._rotate_api_key(force=True)
            return self.get_price(symbol)  # Retry with new key

        if "price" in data:
            return float(data["price"])
        else:
            raise Exception(f"TwelveData API error: {data}")

    def get_ohlc(self, symbol: str, interval: str, outputsize: int = 200):
        self._rotate_api_key()
        normalized_symbol = self.normalize_symbol(symbol)

        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": normalized_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self.current_api_key,
            "format": "JSON"
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        # Handle API limit error
        if "code" in data and data["code"] == 429:
            print("[TwelveData] Rate limit hit, rotating API key...")
            self._rotate_api_key(force=True)
            return self.get_ohlc(symbol, interval, outputsize)  # Retry with new key

        if "values" in data:
            return list(reversed(data["values"]))
        else:
            raise Exception(f"TwelveData API error: {data.get('message', 'Unknown error')}")
