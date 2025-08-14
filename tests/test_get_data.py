import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from utils.get_data import get_price

def test_get_price_litefinance_string():
    """
    Test that get_price correctly parses LiteFinance string response
    and returns a dictionary with 'price', 'bid', 'ask'.
    """
    symbol = "EURUSD"
    result = get_price(symbol)
    
    assert result is not None, "get_price returned None"
    assert isinstance(result, dict), "get_price did not return a dict"
    assert "price" in result, "'price' key missing in get_price result"
    assert "bid" in result, "'bid' key missing in get_price result"
    assert "ask" in result, "'ask' key missing in get_price result"
    assert result["price"] is not None, "Price value is None"
    assert result["bid"] is not None, "Bid value is None"
    assert result["ask"] is not None, "Ask value is None"


# def test_get_price_from_litefinance_success():
#     mock_response = MagicMock()
#     mock_response.json.return_value = {"price": "123.45"}

#     with patch("utils.get_data.get_last_data", return_value=mock_response):
#         price_info = get_data.get_price("EURUSD")

#     assert price_info["source"] == "litefinance scraped last data"
#     assert price_info["symbol"] == "EURUSD"
#     assert price_info["price"] == 123.45


# def test_get_ohlc_from_litefinance_success():
#     ohlc_data = [
#         {"time": 1690000000, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
#         {"time": 1690000015, "open": 1.15, "high": 1.25, "low": 1.1, "close": 1.2},
#     ]

#     mock_resp = MagicMock()
#     mock_resp.json.return_value = {"data": ohlc_data}
#     mock_resp.raise_for_status.return_value = None

#     with patch("utils.get_data.requests.get", return_value=mock_resp), \
#          patch("utils.get_data.normalize_ohlc", return_value=pd.DataFrame(ohlc_data)):
#         df = get_data.get_ohlc("EURUSD", timeframe=15)

#     assert isinstance(df, pd.DataFrame)
#     assert not df.empty


