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

    def _rotate_api_key(self):
        """Rotate the API key every 6 hours."""
        if datetime.now() - self.last_rotation_time > timedelta(hours=6):
            self.current_api_key = next(self.api_keys)
            self.last_rotation_time = datetime.now()

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Convert user input into TwelveData format:
        Examples:
            eurusd  -> EUR/USD
            EURUSD  -> EUR/USD
            eur/usd -> EUR/USD
        """
        cleaned = symbol.replace("/", "").upper()  # Remove slash, uppercase
        if len(cleaned) == 6:
            return f"{cleaned[0:3]}/{cleaned[3:6]}"
        else:
            raise ValueError(f"Invalid currency pair format: {symbol}")

    def get_price(self, symbol: str):
        """
        Fetch the real-time price for a given currency pair.
        """
        self._rotate_api_key()
        normalized_symbol = self.normalize_symbol(symbol)

        url = "https://api.twelvedata.com/price"
        params = {
            "symbol": normalized_symbol,
            "apikey": self.current_api_key
        }

        response = requests.get(url, params=params)
        data = response.json()

        if "price" in data:
            return float(data["price"])
        else:
            raise Exception(f"TwelveData API error: {data}")

