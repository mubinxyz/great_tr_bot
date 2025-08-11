import pytest
from unittest.mock import patch
from handlers import chart

# Dummy classes to mock Telegram update and message
class DummyMessage:
    def __init__(self):
        self.photo = None
        self.filename = None
        self.caption = None
        self.text = None

    async def reply_photo(self, photo, filename, caption=None):
        self.photo = photo
        self.filename = filename
        self.caption = caption

    async def reply_text(self, text):
        self.text = text

class DummyUpdate:
    def __init__(self):
        self.message = DummyMessage()

# --- Test normalize_interval function ---

@pytest.mark.parametrize("input_tf,expected", [
    ("15", "15min"),
    ("15m", "15min"),
    ("4h", "4h"),
    ("1h", "1h"),
    ("1d", "1day"),
    ("1day", "1day"),
    ("day", "1day"),
    ("1w", "1week"),
    ("1week", "1week"),
    ("1mo", "1month"),
    ("1month", "1month"),
    ("month", "1month"),
])
def test_normalize_interval_valid(input_tf, expected):
    assert chart.normalize_interval(input_tf) == expected

@pytest.mark.parametrize("invalid_tf", ["", "abc", "123x", "10q"])
def test_normalize_interval_invalid(invalid_tf):
    with pytest.raises(ValueError):
        chart.normalize_interval(invalid_tf)

# --- Test generate_and_send_chart function ---

@pytest.mark.asyncio
@patch("services.twelvedata_service.TwelveDataService.get_ohlc")
@patch("handlers.chart.mpf.plot")
async def test_generate_and_send_chart(mock_mpf_plot, mock_get_ohlc):
    # Arrange
    mock_get_ohlc.return_value = [
        {"datetime": "2025-08-10 10:00:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"},
    ] * 200

    mock_mpf_plot.return_value = None

    update = DummyUpdate()

    # Act
    await chart.generate_and_send_chart(update, "EUR/USD", "1h")

    # Assert that photo was sent with correct filename and no errors
    assert update.message.photo is not None
    assert update.message.filename == "EUR/USD_1h.png"

@pytest.mark.asyncio
@patch("services.twelvedata_service.TwelveDataService.get_ohlc")
@patch("handlers.chart.mpf.plot")
async def test_generate_and_send_chart_with_caption(mock_mpf_plot, mock_get_ohlc):
    mock_get_ohlc.return_value = [
        {"datetime": "2025-08-10 10:00:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"},
    ] * 200

    mock_mpf_plot.return_value = None

    update = DummyUpdate()
    await chart.generate_and_send_chart(update, "EUR/USD", "1h")

    assert update.message.photo is not None
    assert update.message.filename == "EUR/USD_1h.png"
    assert update.message.caption == "⏱ Timeframe: 1h, Symbol: EUR/USD"
# ⏱ Timeframe: {interval_norm}, Symbol: {symbol}

print("Using normalize_interval from:", chart.normalize_interval)
print("normalize_interval('month') =", chart.normalize_interval("month"))