# tests/test_get_data.py
import json
import builtins
from unittest.mock import patch, MagicMock
from utils.get_data import DataService

def test_get_price_litefinance_success():
    """Test when LiteFinance scrape works."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"price": "1.2345", "bid": "1.23", "ask": "1.24"})

    with patch("subprocess.run", return_value=mock_result):
        ds = DataService()
        result = ds.get_price("EURUSD")
        assert result["source"] == "litefinance"
        assert result["price"] == 1.2345
        assert result["bid"] == 1.23
        assert result["ask"] == 1.24

def test_get_price_fallback_to_twelvedata():
    """Test when LiteFinance fails but TwelveData succeeds."""
    mock_result = MagicMock()
    mock_result.returncode = 1  # LiteFinance script fails

    mock_td_response = MagicMock()
    mock_td_response.json.return_value = {"price": "1.5678"}
    mock_td_response.raise_for_status = lambda: None

    with patch("subprocess.run", return_value=mock_result), \
         patch("requests.get", return_value=mock_td_response):
        ds = DataService()
        result = ds.get_price("EURUSD")
        assert result["source"] == "twelvedata"
        assert result["price"] == 1.5678

def test_get_price_returns_none_when_both_fail():
    """Test when both LiteFinance and TwelveData fail."""
    mock_result = MagicMock()
    mock_result.returncode = 1  # LiteFinance script fails

    with patch("subprocess.run", return_value=mock_result), \
         patch("requests.get", side_effect=Exception("API error")):
        ds = DataService()
        result = ds.get_price("EURUSD")
        assert result is None
