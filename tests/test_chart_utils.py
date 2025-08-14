# tests/test_chart_utils.py
import io
import pytest
import numpy as np
import pandas as pd
from datetime import datetime

# function under test
from utils.chart_utils import generate_chart_image


# Helpers ---------------------------------------------------------------
def _make_ohlc_df(n=50, freq="15T"):
    """
    Create a synthetic OHLC DataFrame with a DatetimeIndex (UTC) and columns:
    ['open', 'high', 'low', 'close', 'volume'].
    """
    # use now(tz="UTC") to be safe across pandas versions
    end = pd.Timestamp.now(tz="UTC")
    idx = pd.date_range(end=end, periods=n, freq=freq, tz="UTC")
    rng = np.random.default_rng(0)
    base = 1.1000 + np.cumsum(rng.normal(scale=0.0005, size=n))
    open_prices = base
    close_prices = base + rng.normal(scale=0.0002, size=n)
    high_prices = np.maximum(open_prices, close_prices) + np.abs(rng.normal(scale=0.0003, size=n))
    low_prices = np.minimum(open_prices, close_prices) - np.abs(rng.normal(scale=0.0003, size=n))
    volume = (rng.integers(1, 1000, size=n)).astype(int)
    df = pd.DataFrame({
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume
    }, index=idx)
    return df


# Tests -----------------------------------------------------------------
def test_generate_chart_image_from_dataframe(monkeypatch):
    """DataFrame input path should produce a PNG buffer and return timeframe."""
    df = _make_ohlc_df(n=60, freq="15T")
    import utils.chart_utils as cu
    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: df)

    buf, period = generate_chart_image("EURUSD", alert_price=None, timeframe="15", from_date=None, to_date=None, outputsize=50)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0
    assert str(period) == "15"


def test_generate_chart_image_from_records_with_datetime(monkeypatch):
    """
    get_ohlc may return a list-of-dicts where each dict has a 'datetime' key.
    The function should accept that and produce a PNG buffer.
    """
    df = _make_ohlc_df(n=40, freq="15T")
    records = df.reset_index().rename(columns={"index": "datetime"}).to_dict("records")

    import utils.chart_utils as cu
    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: records)

    buf, period = generate_chart_image("EURUSD", alert_price=None, timeframe="15", from_date=None, to_date=None, outputsize=40)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0
    assert str(period) == "15"


def test_generate_chart_image_from_prepared_list_of_lists_df(monkeypatch):
    """
    Some providers might yield list-of-lists, but the real get_ohlc normalizes those into
    a DataFrame. Simulate that by returning a DataFrame derived from list-of-lists.
    """
    df = _make_ohlc_df(n=30, freq="15T")
    rows = []
    for ts, row in df.iterrows():
        rows.append([int(ts.timestamp()), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), int(row["volume"])])

    # Build the DataFrame exactly how generate_chart_image expects it (datetime index and OHLC columns)
    df_rows = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    df_rows["datetime"] = pd.to_datetime(df_rows["datetime"], unit="s", utc=True)
    df_rows = df_rows.set_index("datetime")

    import utils.chart_utils as cu
    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: df_rows)

    buf, period = generate_chart_image("EURUSD", alert_price=1.12, timeframe="15", from_date=None, to_date=None, outputsize=30)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0
    assert str(period) == "15"


def test_generate_chart_image_empty_or_none_raises(monkeypatch):
    """If get_ohlc returns empty sequence or None, we expect ValueError('No OHLC data returned')."""
    import utils.chart_utils as cu
    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: [])
    with pytest.raises(ValueError):
        generate_chart_image("EURUSD", timeframe="15", from_date=None, to_date=None, outputsize=10)

    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: None)
    with pytest.raises(ValueError):
        generate_chart_image("EURUSD", timeframe="15", from_date=None, to_date=None, outputsize=10)


def test_generate_chart_image_get_ohlc_raises_runtime(monkeypatch):
    """If underlying get_ohlc raises, generate_chart_image should raise RuntimeError."""
    import utils.chart_utils as cu

    def _boom(*args, **kwargs):
        raise Exception("provider boom")

    monkeypatch.setattr(cu, "get_ohlc", _boom)

    with pytest.raises(RuntimeError):
        generate_chart_image("EURUSD", timeframe="15", from_date=None, to_date=None, outputsize=10)


def test_generate_chart_image_with_alert_price(monkeypatch):
    """Adding an alert_price addplot should still produce a PNG buffer."""
    df = _make_ohlc_df(n=50, freq="15T")
    import utils.chart_utils as cu
    monkeypatch.setattr(cu, "get_ohlc", lambda *args, **kwargs: df)

    buf, period = generate_chart_image("EURUSD", alert_price=1.12, timeframe="15", from_date=None, to_date=None, outputsize=50)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0
    assert str(period) == "15"
