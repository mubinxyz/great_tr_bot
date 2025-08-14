import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from utils import get_data


@pytest.fixture(autouse=True)
def reset_api_keys():
    """
    Reset API key globals before each test
    so rotation logic is predictable.
    """
    get_data._td_api_keys = iter(["KEY1", "KEY2", "KEY3"])
    get_data._current_api_key = next(get_data._td_api_keys)
    get_data._last_rotation_time = get_data.datetime.now()


def test_get_price_from_litefinance_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"price": "123.45"}

    with patch("utils.get_data.get_last_data", return_value=mock_response):
        price_info = get_data.get_price("EURUSD")

    assert price_info["source"] == "litefinance scraped last data"
    assert price_info["symbol"] == "EURUSD"
    assert price_info["price"] == 123.45


def test_get_price_from_twelvedata_fallback():
    # Simulate LiteFinance scrape failure
    with patch("utils.get_data.get_last_data", side_effect=Exception("Scrape failed")), \
         patch("utils.get_data.requests.get") as mock_get:

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"price": "456.78"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        price_info = get_data.get_price("GBPUSD")

    assert price_info["source"] == "twelvedata"
    assert price_info["price"] == 456.78


def test_get_ohlc_from_litefinance_success():
    ohlc_data = [
        {"time": 1690000000, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
        {"time": 1690000015, "open": 1.15, "high": 1.25, "low": 1.1, "close": 1.2},
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": ohlc_data}
    mock_resp.raise_for_status.return_value = None

    with patch("utils.get_data.requests.get", return_value=mock_resp), \
         patch("utils.get_data.normalize_ohlc", return_value=pd.DataFrame(ohlc_data)):
        df = get_data.get_ohlc("EURUSD", timeframe=15)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_ohlc_from_twelvedata_fallback():
    # Simulate LiteFinance failure
    with patch("utils.get_data.requests.get") as mock_get:
        # First call (LiteFinance) raises exception
        mock_get.side_effect = [
            Exception("LiteFinance failed"),
            MagicMock(**{
                "json.return_value": {
                    "values": [
                        {"datetime": "2024-08-01 00:00:00", "open": "1.1", "high": "1.2", "low": "1.0", "close": "1.15"},
                        {"datetime": "2024-08-01 00:15:00", "open": "1.15", "high": "1.25", "low": "1.1", "close": "1.2"}
                    ]
                },
                "raise_for_status.return_value": None
            })
        ]

        df = get_data.get_ohlc("GBPUSD", timeframe=15)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "datetime" in df.columns
