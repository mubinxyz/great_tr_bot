# utils/normalize_data.py

import pandas as pd


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

    LiteFinance accepts:
        1, 5, 15, 30, 60, 240, D, W, M

    Args:
        tf: timeframe as int or string (e.g. 15, "15m", "daily", "D")

    Returns:
        str: normalized timeframe code
    """
    tf_map = {
        "1": "1", "1m": "1", 1: "1",
        "5": "5", "5m": "5", 5: "5",
        "15": "15", "15m": "15", 15: "15",
        "30": "30", "30m": "30", 30: "30",
        "60": "60", "1h": "60", 60: "60",
        "240": "240", "4h": "240", 240: "240",
        "D": "D", "1d": "D", "daily": "D", "day": "D",
        "W": "W", "1w": "W", "weekly": "W", "week": "W",
        "M": "M", "1mo": "M", "monthly": "M", "month": "M"
    }

    key = str(tf).lower()
    return tf_map.get(key, "15")  # default to 15 min


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