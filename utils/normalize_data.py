# utils/normalize_data.py

import pandas as pd


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a trading symbol by stripping spaces and converting to uppercase.

    Args:
        symbol (str): The trading symbol, e.g., ' eurusd ', 'BTC-USD'.

    Returns:
        str: Normalized symbol in uppercase, e.g., 'EURUSD', 'BTC-USD'.
    """
    if not symbol:
        return ""
    return symbol.strip().upper()


def normalize_ohlc(content: list) -> pd.DataFrame:
    """
    Normalize LiteFinance-style OHLC data into a pandas DataFrame.

    LiteFinance API format:
        [
            [timestamp_ms, open, high, low, close],
            ...
        ]

    Args:
        content (list): List of OHLC rows from LiteFinance.

    Returns:
        pd.DataFrame: Columns = ['datetime', 'open', 'high', 'low', 'close']
    """
    if not content or not isinstance(content, list):
        raise ValueError("Invalid OHLC data: must be a non-empty list.")

    df = pd.DataFrame(content, columns=["timestamp_ms", "open", "high", "low", "close"])

    # Convert timestamp to datetime (UTC)
    df["datetime"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)

    # Drop original timestamp column
    df.drop(columns=["timestamp_ms"], inplace=True)

    # Ensure numeric conversion
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with NaN values
    df.dropna(inplace=True)

    # Sort chronologically
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df