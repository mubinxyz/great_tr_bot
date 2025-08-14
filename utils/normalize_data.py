# utils/normalize_data.py

import pandas as pd
from datetime import datetime


def normalize_symbol(symbol: str) -> str:
    """
    Normalize trading symbol for API requests.
    - Removes spaces and slashes
    - Converts to uppercase

    Args:
        symbol (str): raw symbol like "eurusd", "EUR/USD", "eur usd"

    Returns:
        str: normalized symbol (e.g., "EURUSD")
    """
    if not symbol:
        return ""
    return symbol.replace(" ", "").replace("/", "").upper()


def normalize_timeframe(tf) -> str:
    """
    Normalize timeframe to LiteFinance/TwelveData format.

    LiteFinance accepts minute codes: "1", "5", "15", "30", "60", "240"
    and period codes: "D", "W", "M".

    Accepts inputs like: 15, "15m", "1h", "daily", "D", "d", "1", 1, etc.

    Returns:
        str: normalized timeframe code (e.g. "15", "60", "D", "W", "M")
    """
    if tf is None:
        return "15"

    key = str(tf).strip().lower()

    tf_map = {
        # minutes
        "1": "1", "1m": "1", "min": "1", "mins": "1",
        "5": "5", "5m": "5",
        "15": "15", "15m": "15",
        "30": "30", "30m": "30",
        "60": "60", "1h": "60", "h": "60",
        "240": "240", "4h": "240",

        # days / weeks / months -> return uppercase canonical values
        "d": "D", "1d": "D", "daily": "D", "day": "D",
        "w": "W", "1w": "W", "weekly": "W", "week": "W",
        "m": "M", "1mo": "M", "monthly": "M", "month": "M",
    }

    # allow keys like "15min" or "15mn" by stripping common suffixes
    if key.endswith("min") or key.endswith("mins") or key.endswith("mn"):
        key = key.replace("mins", "").replace("min", "").replace("mn", "")

    # allow keys like "15m", "1h" already handled above, but this helps integer-like strings
    if key.isdigit():
        # keep as-is if it's a recognized minute interval
        if key in {"1", "5", "15", "30", "60", "240"}:
            return key
        # otherwise fallback to 15
        return "15"

    # lookup in map, default to 15 minutes
    return tf_map.get(key, "15")

def normalize_ohlc(ohlc_data: dict) -> pd.DataFrame:
    """
    Normalize OHLC data into a Pandas DataFrame.
    Handles missing volume gracefully.

    Args:
        ohlc_data (dict): Dictionary containing keys 'o', 'h', 'l', 'c', optionally 'v' and 't'.

    Returns:
        pd.DataFrame: DataFrame with columns ['datetime', 'open', 'high', 'low', 'close', 'volume' (if available)].
    """
    if not ohlc_data:
        return pd.DataFrame()

    df = pd.DataFrame({
        "datetime": pd.to_datetime(ohlc_data.get("t", []), unit="s", utc=True),
        "open": pd.to_numeric(ohlc_data.get("o", []), errors="coerce"),
        "high": pd.to_numeric(ohlc_data.get("h", []), errors="coerce"),
        "low": pd.to_numeric(ohlc_data.get("l", []), errors="coerce"),
        "close": pd.to_numeric(ohlc_data.get("c", []), errors="coerce"),
    })

    # Add volume if present
    if "v" in ohlc_data:
        df["volume"] = pd.to_numeric(ohlc_data.get("v", []), errors="coerce")

    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df



def to_unix_timestamp(time_input) -> int | None:
    """
    Convert many date/time inputs to a Unix timestamp (seconds).
    - Returns int(seconds) or None if input is None.

    Accepts:
      - datetime.datetime
      - pandas.Timestamp
      - int/float (seconds or milliseconds)
      - strings in many formats, e.g.:
          "2025-01-01", "2025-01-01 14:30:00", "2025-01-01,14:30:00",
          "2025-01-01T14:30:00", ISO strings, "now"
    Raises:
      ValueError for unrecognized strings, TypeError for unsupported types.
    """
    if time_input is None:
        return None

    # datetime
    if isinstance(time_input, datetime):
        return int(time_input.timestamp())

    # pandas Timestamp
    if isinstance(time_input, pd.Timestamp):
        return int(time_input.timestamp())

    # numbers (seconds or milliseconds)
    if isinstance(time_input, (int, float)):
        # avoid bool (subclass of int) confusion
        if isinstance(time_input, bool):
            raise TypeError(f"Unsupported type: {type(time_input)}")
        val = float(time_input)
        # heuristics: >1e12 -> milliseconds
        if val > 1e12:
            return int(val // 1000)
        return int(val)

    # strings
    if isinstance(time_input, str):
        s = time_input.strip()
        if not s:
            raise ValueError("Empty date string")

        lower = s.lower()
        if lower in ("now", "current", "today"):
            return int(_time.time())

        # Accept comma-separated date/time like "2024-08-01,14:30:00"
        # and ISO-like "2024-08-01T14:30:00"
        cleaned = s.replace(",", " ").replace("T", " ").strip()

        # Try pandas robust parser first (uses dateutil under the hood)
        try:
            ts = pd.to_datetime(cleaned, utc=True)
            if pd.isna(ts):
                raise ValueError("parsed to NaT")
            return int(ts.timestamp())
        except Exception:
            # Fallback: try several common strptime formats (local naive)
            fmts = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y",
            ]
            for fmt in fmts:
                try:
                    dt = datetime.strptime(cleaned, fmt)
                    # treat as UTC (or naive local) -> convert to epoch seconds
                    return int(dt.replace(tzinfo=None).timestamp())
                except Exception:
                    continue

            # if still failing, raise so caller can report proper message
            raise ValueError(f"Unrecognized date/time format: {time_input}")

    # unsupported type
    raise TypeError(f"Unsupported type: {type(time_input)}")