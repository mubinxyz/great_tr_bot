# tests/test_get_data.py

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from utils.get_data import DataService

@pytest.fixture
def data_service():
    return DataService()

# ---------------------------
# Test get_price
# ---------------------------
@patch("utils.get_data.fetch_last_price_json")
def test_get_price_litefinance_success(mock_fetch, data_service):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"price": "123.45"}
    mock_fetch.return_value = mock_resp

    result = data_service.get_price("EURUSD")
    assert result["source"].startswith("litefinance")
    assert result["price"] == 123.45
    assert result["symbol"] == "EURUSD"

@patch("utils.get_data.fetch_last_price_json", side_effect=Exception("fail"))
@patch("utils.get_data.requests.get")
def test_get_price_twelvedata_fallback(mock_get, mock_fetch, data_service):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"price": "678.90"}
    mock_get.return_value = mock_resp

    result = data_service.get_price("EURUSD")
    assert result["source"] == "twelvedata"
    assert result["price"] == 678.90
    assert result["symbol"] == "EURUSD"

@patch("utils.get_data.fetch_last_price_json", side_effect=Exception("fail"))
@patch("utils.get_data.requests.get", side_effect=Exception("fail"))
def test_get_price_none(mock_get, mock_fetch, data_service):
    result = data_service.get_price("EURUSD")
    assert result is None

# ---------------------------
# Test get_ohlc
# ---------------------------
@patch("utils.get_data.normalize_ohlc")
@patch("utils.get_data.requests.get")
def test_get_ohlc_litefinance_success(mock_get, mock_normalize, data_service):
    # LiteFinance raw data
    lite_data = [{"t": 1, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 100}]
    mock_get.return_value = MagicMock()
    mock_get.return_value.json.return_value = {"data": lite_data}

    # normalized DataFrame returned by normalize_ohlc
    mock_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2025-08-13")],
        "open": [1.0],
        "high": [2.0],
        "low": [0.5],
        "close": [1.5],
        "volume": [100]
    })
    mock_normalize.return_value = mock_df

    df = data_service.get_ohlc("EURUSD")
    assert isinstance(df, pd.DataFrame)
    assert "open" in df.columns
    assert df["open"].iloc[0] == 1.0

@patch("utils.get_data.requests.get")
def test_get_ohlc_twelvedata_fallback(mock_get, data_service):
    # TwelveData fallback mock
    td_mock = MagicMock()
    td_values = [
        {"datetime": "2025-08-13 00:00:00", "open": "1.0", "high": "2.0", "low": "0.5", "close": "1.5"}
    ]
    td_mock.json.return_value = {"values": td_values}

    # side_effect function: first call raises LiteFinance fail, second returns TD mock
    def side_effect(url, *args, **kwargs):
        if "litefinance" in url:
            raise Exception("LiteFinance fail")
        return td_mock

    mock_get.side_effect = side_effect

    df = data_service.get_ohlc("EURUSD")
    assert isinstance(df, pd.DataFrame)
    assert df["open"].iloc[0] == 1.0
    assert pd.api.types.is_datetime64_any_dtype(df["datetime"])

@patch("utils.get_data.requests.get", side_effect=Exception("fail"))
def test_get_ohlc_fail_returns_empty(mock_get, data_service):
    df = data_service.get_ohlc("EURUSD")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
