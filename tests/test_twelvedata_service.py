# tests/test_twelvedata_service.py
import pytest
from services.twelvedata_service import TwelveDataService

def test_normalize_symbol_lowercase():
    assert TwelveDataService.normalize_symbol("eurusd") == "EUR/USD"

def test_normalize_symbol_uppercase():
    assert TwelveDataService.normalize_symbol("EURUSD") == "EUR/USD"

def test_normalize_symbol_with_slash():
    assert TwelveDataService.normalize_symbol("eur/usd") == "EUR/USD"

def test_normalize_symbol_invalid_length():
    with pytest.raises(ValueError):
        TwelveDataService.normalize_symbol("euru")

def test_normalize_symbol_random_string():
    with pytest.raises(ValueError):
        TwelveDataService.normalize_symbol("1234567")
