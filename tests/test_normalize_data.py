# tests/test_normalize_data.py

import pytest
import pandas as pd
from utils.normalize_data import normalize_symbol, normalize_ohlc


def test_normalize_symbol_basic():
    assert normalize_symbol(" eurusd ") == "EURUSD"
    assert normalize_symbol("btc-usd") == "BTC-USD"
    assert normalize_symbol("") == ""
    assert normalize_symbol(None) == ""


def test_normalize_ohlc_valid():
    # Example LiteFinance OHLC data (timestamp_ms, open, high, low, close)
    content = [
        [1723526400000, "1.1000", "1.1100", "1.0900", "1.1050"],
        [1723612800000, "1.1050", "1.1150", "1.0950", "1.1100"],
    ]

    df = normalize_ohlc(content)

    # Check DataFrame structure
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "datetime"]

    # Check datetime conversion
    assert pd.api.types.is_datetime64_any_dtype(df["datetime"])
    assert str(df["datetime"].dt.tz) == "UTC"

    # Check numeric conversion
    assert pd.api.types.is_float_dtype(df["open"])

    # Check row count
    assert len(df) == 2

    # Ensure chronological order
    assert df["datetime"].is_monotonic_increasing


def test_normalize_ohlc_invalid():
    with pytest.raises(ValueError):
        normalize_ohlc([])

    with pytest.raises(ValueError):
        normalize_ohlc(None)

    with pytest.raises(ValueError):
        normalize_ohlc("invalid data")
