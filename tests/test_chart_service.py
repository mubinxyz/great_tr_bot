# tests/test_chart_service.py
import pytest
from services.chart_service import get_chart
from io import BytesIO

def test_get_chart_basic():
    """Test that get_chart returns a BytesIO buffer and a valid timeframe."""
    symbol = "EURUSD"
    timeframe = 15

    # Pass None for optional args
    buf, period = get_chart(
        symbol,
        timeframe=timeframe,
        alert_price=None,
        outputsize=200,
        from_date=None,
        to_date=None
    )

    # Check types
    assert isinstance(buf, BytesIO), "Chart buffer should be BytesIO"
    assert period in [1, 5, 15, 30, 60, 240, "D", "W", "M"], "Returned timeframe is invalid"

    # Optionally check buffer is not empty
    buf_content = buf.getvalue()
    assert len(buf_content) > 0, "Chart buffer is empty"
