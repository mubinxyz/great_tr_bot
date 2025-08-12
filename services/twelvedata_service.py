# services/twelvedata_service.py (updated)
import requests
from datetime import datetime, timedelta
from config import TD_API_KEYS
import itertools
import time
from typing import Optional


class TwelveDataService:
    def __init__(self):
        self.api_keys = itertools.cycle(TD_API_KEYS)  # Rotate keys cyclically
        self.current_api_key = next(self.api_keys)
        self.last_rotation_time = datetime.now()
        self._symbol_cache = {}  # simple in-memory cache: user_input -> resolved_symbol

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
        params = params.copy()
        params["apikey"] = self.current_api_key

        url = f"https://api.twelvedata.com/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
        except Exception as exc:
            raise RuntimeError(f"[TwelveData] HTTP error for {url}: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            raise RuntimeError(f"[TwelveData] non-json response: {response.text}")

        # Handle rate / quota errors
        if isinstance(data, dict):
            code = data.get("code")
            message = (data.get("message") or "").lower()
            if code == 429 or "run out of api credits" in message or "rate limit" in message:
                print(f"[TwelveData] Rate/credit limit hit for key {self.current_api_key}: {message}")
                if retry:
                    self._force_rotate_api_key()
                    # tiny sleep to avoid 429 loops
                    time.sleep(0.2)
                    return self._request(endpoint, params, retry=False)
        return data

    # -------------------------
    # symbol resolution utilities
    # -------------------------
    @staticmethod
    def _is_simple_forex(s: str) -> bool:
        s = s.strip()
        return len(s) == 6 and s.isalpha()

    def _search_symbol_api(self, query: str) -> Optional[list]:
        """Call TwelveData symbol_search reference endpoint and return candidate list (or None)."""
        try:
            data = self._request("symbol_search", {"symbol": query})
        except Exception:
            return None

        # response formats vary; try to find an array of candidates robustly
        candidates = None
        if isinstance(data, dict):
            for key in ("data", "symbols", "result", "items", "matches"):
                if key in data and isinstance(data[key], list):
                    candidates = data[key]
                    break
            # some docs show a top-level list directly in the dict under no wrapper
            if candidates is None:
                # sometimes API returns {"status":"ok","data": [...]} or {"status":"ok", "result": [...]}
                if "status" in data and isinstance(data.get("data"), list):
                    candidates = data.get("data")
        elif isinstance(data, list):
            candidates = data

        return candidates

    def resolve_symbol(self, raw_symbol: str) -> str:
        """
        Robustly resolve user input -> TwelveData symbol.
        Uses heuristics first (slashes, forex, common commodity/index maps).
        Then tries symbol_search reference lookup (recommended by TwelveData docs).
        Caches results.
        """
        if not raw_symbol:
            raise ValueError("Empty symbol")

        key = raw_symbol.strip()
        if key in self._symbol_cache:
            return self._symbol_cache[key]

        s = key.strip().upper()

        # Already canonical (contains slash or colon)
        if "/" in s or ":" in s:
            self._symbol_cache[key] = s
            return s

        # common forex shorthand (EURUSD -> EUR/USD)
        if self._is_simple_forex(s):
            resolved = f"{s[0:3]}/{s[3:6]}"
            self._symbol_cache[key] = resolved
            return resolved

        # quick commodity shorthands (optional convenience)
        commodity_map = {
            "XAU": "XAU/USD",  # gold
            "GOLD": "XAU/USD",
            "XAG": "XAG/USD",  # silver
            "SILVER": "XAG/USD",
            "WTI": "WTI/USD",
            "BRENT": "BRENT/USD",
            "OIL": "WTI/USD",
        }
        if s in commodity_map:
            self._symbol_cache[key] = commodity_map[s]
            return commodity_map[s]

        # quick index aliases (common)
        index_map = {
            "DOW": "DJI:INDEX",
            "DJI": "DJI:INDEX",
            "DJIA": "DJI:INDEX",
            "SPX": "SPX:INDEX",
            "SP500": "SPX:INDEX",
            "S&P500": "SPX:INDEX",
            "NASDAQ": "NDX:INDEX",
            "NDX": "NDX:INDEX",
            "DAX": "DAX:INDEX",
            "FTSE": "FTSE:INDEX",
            "NIKKEI": "N225:INDEX",
        }
        if s in index_map:
            self._symbol_cache[key] = index_map[s]
            return index_map[s]

        # last resort: query TwelveData symbol_search to find canonical symbol
        candidates = self._search_symbol_api(s)
        if candidates:
            # prefer exact-symbol matches (case-insensitive) first
            for c in candidates:
                sym = (c.get("symbol") or c.get("ticker") or "").upper()
                if sym == s:
                    self._symbol_cache[key] = sym
                    return sym

            # prefer Index/Commodity/Stock by checking likely fields
            preferred_types = ["index", "commodity", "stock", "etf", "crypto", "forex"]
            for p in preferred_types:
                for c in candidates:
                    # look for a type-like field in candidate
                    typ = (c.get("type") or c.get("instrument_type") or c.get("category") or c.get("asset_type") or "")
                    if isinstance(typ, str) and p in typ.lower():
                        resolved = (c.get("symbol") or c.get("ticker") or "").upper()
                        if resolved:
                            self._symbol_cache[key] = resolved
                            return resolved

            # fallback: return the first candidate.symbol
            first = candidates[0]
            resolved = (first.get("symbol") or first.get("ticker") or "").upper()
            if resolved:
                self._symbol_cache[key] = resolved
                return resolved

        # final fallback: return input uppercased (best-effort)
        self._symbol_cache[key] = s
        return s

    # -------------------------
    # public data methods
    # -------------------------
    def get_price(self, symbol: str):
        """Fetch real-time price."""
        resolved = self.resolve_symbol(symbol)
        data = self._request("price", {"symbol": resolved})
        if "price" in data:
            return float(data["price"])
        else:
            raise Exception(f"TwelveData API error: {data}")

    def get_ohlc(self, symbol: str, interval: str, outputsize: int = 200):
        """Fetch OHLC candlestick data."""
        resolved = self.resolve_symbol(symbol)
        data = self._request("time_series", {
            "symbol": resolved,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON"
        })

        if "values" in data:
            return list(reversed(data["values"]))  # Reverse so oldest first
        else:
            raise Exception(f"TwelveData API error: {data.get('message', 'Unknown error')}")
