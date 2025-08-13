# tests/test_chart_utils.py
import pytest
import pandas as pd
from io import BytesIO
from unittest.mock import patch
from utils import chart_utils


# --- Sample OHLC data for mocking ---
SAMPLE_OHLC = [
    {"datetime": "2025-08-01T00:00:00Z", "open": 100, "high": 110, "low": 90, "close": 105},
    {"datetime": "2025-08-01T01:00:00Z", "open": 105, "high": 115, "low": 95, "close": 110},
    {"datetime": "2025-08-01T02:00:00Z", "open": 110, "high": 120, "low": 100, "close": 115},
]


def test_normalize_interval_minutes():
    assert chart_utils.normalize_interval("1") == 1
    assert chart_utils.normalize_interval("5m") == 5
    assert chart_utils.normalize_interval("1h") == 60
    assert chart_utils.normalize_interval("1d") == 1440
    assert chart_utils.normalize_interval("1w") == 10080
    assert chart_utils.normalize_interval("1mo") == 43200
    assert chart_utils.normalize_interval(15) == 15

    with pytest.raises(ValueError):
        chart_utils.normalize_interval("invalid")


@patch("utils.chart_utils.data_service")
def test_generate_chart_image_basic(mock_data_service):
    mock_data_service.get_ohlc.return_value = SAMPLE_OHLC

    buf, period = chart_utils.generate_chart_image("BTCUSD", "1h")
    
    # Ensure we get the correct period in minutes
    assert period == 60

    # Ensure buffer is BytesIO and non-empty
    assert isinstance(buf, BytesIO)
    buf.seek(0)
    assert len(buf.read()) > 0


@patch("utils.chart_utils.data_service")
def test_generate_chart_image_with_alert(mock_data_service):
    mock_data_service.get_ohlc.return_value = SAMPLE_OHLC

    buf, period = chart_utils.generate_chart_image("BTCUSD", "1h", alert_price=108)
    
    # Check period is correct
    assert period == 60
    
    # Buffer should be valid
    assert isinstance(buf, BytesIO)
    buf.seek(0)
    assert len(buf.read()) > 0


@patch("utils.chart_utils.data_service")
def test_generate_chart_image_invalid_ohlc(mock_data_service):
    # Simulate empty response
    mock_data_service.get_ohlc.return_value = []

    with pytest.raises(ValueError, match="No OHLC data returned"):
        chart_utils.generate_chart_image("BTCUSD", "1h")


@patch("utils.chart_utils.data_service")
def test_generate_chart_image_exception(mock_data_service):
    # Simulate exception from DataService
    mock_data_service.get_ohlc.side_effect = RuntimeError("API error")

    with pytest.raises(RuntimeError, match="Failed to fetch OHLC"):
        chart_utils.generate_chart_image("BTCUSD", "1h")

@pytest.mark.visual
def test_generate_chart_image_file(tmp_path):
    """
    Visual test: generate chart and save to temp directory.
    This does not affect your main environment.
    """
    symbol = "BTCUSD"
    interval = "1h"
    alert_price = 120000

    buf, _ = chart_utils.generate_chart_image(symbol, interval, alert_price=alert_price)
    
    # Save to temporary file
    temp_file = tmp_path / "btc_chart.png"
    with open(temp_file, "wb") as f:
        f.write(buf.getbuffer())

    print(f"Chart saved temporarily at: {temp_file}")
    assert temp_file.exists() and temp_file.stat().st_size > 0