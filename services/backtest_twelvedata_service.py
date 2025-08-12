import requests
from datetime import datetime, timedelta
import itertools
from config import TD_STRATEGY_API_KEYS

class BacktestTwelveDataService:
    """
    Uses TD_STRATEGY_API_KEYS for backtesting (separate from production alerts).
    Handles key rotation, daily-limit blocking, and 429 retry.
    """

    def __init__(self):
        if not TD_STRATEGY_API_KEYS:
            raise RuntimeError("No TD_STRATEGY_API_KEYS configured in config.py or .env")
        self.api_keys = list(TD_STRATEGY_API_KEYS)
        self._cycle = itertools.cycle(self.api_keys)
        self.current_api_key = next(self._cycle)
        self.last_rotation_time = datetime.now()
        self.blocked_keys = {}

    def _clean_blocked(self):
        now = datetime.now()
        expired = [k for k, until in self.blocked_keys.items() if until <= now]
        for k in expired:
            del self.blocked_keys[k]

    def _get_next_unblocked(self, force=False):
        self._clean_blocked()
        for _ in range(len(self.api_keys)):
            k = next(self._cycle)
            if k not in self.blocked_keys and (not force or k != self.current_api_key):
                self.current_api_key = k
                self.last_rotation_time = datetime.now()
                return k
        if self.current_api_key not in self.blocked_keys:
            return self.current_api_key
        return None

    def _force_rotate(self):
        k = self._get_next_unblocked(force=True)
        if k is None:
            raise RuntimeError("No available backtest API keys (all blocked)")
        return k

    def _rotate_if_time(self):
        if datetime.now() - self.last_rotation_time > timedelta(hours=6):
            self._get_next_unblocked(force=True)

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        cleaned = symbol.replace("/", "").upper()
        if len(cleaned) == 6:
            return f"{cleaned[0:3]}/{cleaned[3:6]}"
        return symbol.upper()

    def _request(self, endpoint: str, params: dict, retry: bool = True):
        self._rotate_if_time()
        params["apikey"] = self.current_api_key
        url = f"https://api.twelvedata.com/{endpoint}"
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        # Handle 429 per-minute
        if "code" in data and data["code"] == 429:
            if retry:
                self._force_rotate()
                params["apikey"] = self.current_api_key
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()

        # Daily limit detection
        msg = str(data.get("message", "")).lower()
        if "run out of api credits" in msg or "out of api credits" in msg:
            self.blocked_keys[self.current_api_key] = datetime.now() + timedelta(days=1)
            if retry:
                self._force_rotate()
                params["apikey"] = self.current_api_key
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()

        return data

    def get_price(self, symbol: str):
        s = self.normalize_symbol(symbol)
        data = self._request("price", {"symbol": s})
        if "price" in data:
            return float(data["price"])
        raise Exception(f"TwelveData error: {data}")

    def get_ohlc(self, symbol: str, interval: str, outputsize: int = 200):
        s = self.normalize_symbol(symbol)
        data = self._request("time_series", {
            "symbol": s,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON"
        })
        if "values" in data:
            return list(reversed(data["values"]))
        raise Exception(f"TwelveData error: {data}")
