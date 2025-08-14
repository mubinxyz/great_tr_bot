import io
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers import alert as alert_handler

VALID_CODES = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}


@pytest.mark.asyncio
async def test_alert_generates_charts_for_each_timeframe(monkeypatch):
    # --- Fake DB & Alert object ---
    fake_user = MagicMock()
    fake_user.id = 123
    fake_alert = MagicMock()
    fake_alert.id = 456
    fake_alert.symbol = "eurusd"
    fake_alert.target_price = 1.2345
    fake_alert.timeframes = ["60", "240"]
    fake_alert.direction = MagicMock(value="above")
    fake_alert.triggered = False

    monkeypatch.setattr(alert_handler, "get_or_create_user", lambda **kwargs: fake_user)
    monkeypatch.setattr(alert_handler, "create_alert", lambda **kwargs: fake_alert)

    # --- Capture chart calls ---
    chart_calls = []

    def fake_chart(symbol, alert_price=None, timeframe=None, **kwargs):
        chart_calls.append((symbol, timeframe))
        buf = io.BytesIO(b"fakepng")
        return buf, timeframe  # timeframe already normalized here

    monkeypatch.setattr(alert_handler, "generate_chart_image", fake_chart)

    # --- Fake Telegram update/context ---
    update = MagicMock()
    update.effective_chat.id = 999
    update.effective_user.username = "user"
    update.effective_user.first_name = "First"
    update.effective_user.last_name = "Last"
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()

    context = MagicMock()
    context.args = ["eurusd", "1.2345", "1h,4h"]

    # --- Run the handler ---
    await alert_handler.alert_command(update, context)

    # --- Assertions ---
    assert len(chart_calls) == 2, "Should call chart generator once per timeframe"
    for symbol, tf in chart_calls:
        assert symbol == "eurusd"
        assert tf in VALID_CODES, f"Invalid LiteFinance timeframe code: {tf}"

    assert update.message.reply_photo.await_count == 2
    assert update.message.reply_text.await_count >= 1


@pytest.mark.asyncio
async def test_alert_handles_no_ohlc_data(monkeypatch):
    fake_user = MagicMock()
    fake_user.id = 123
    fake_alert = MagicMock()
    fake_alert.id = 456
    fake_alert.symbol = "eurusd"
    fake_alert.target_price = 1.2345
    fake_alert.timeframes = ["5"]
    fake_alert.direction = MagicMock(value="below")
    fake_alert.triggered = False

    monkeypatch.setattr(alert_handler, "get_or_create_user", lambda **kwargs: fake_user)
    monkeypatch.setattr(alert_handler, "create_alert", lambda **kwargs: fake_alert)

    def fake_chart_raises(symbol, alert_price=None, timeframe=None, **kwargs):
        raise ValueError("No OHLC data returned")

    monkeypatch.setattr(alert_handler, "generate_chart_image", fake_chart_raises)

    update = MagicMock()
    update.effective_chat.id = 999
    update.effective_user.username = "user"
    update.effective_user.first_name = "First"
    update.effective_user.last_name = "Last"
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()

    context = MagicMock()
    context.args = ["eurusd", "1.2345", "5m"]

    await alert_handler.alert_command(update, context)

    # Should not try to send a photo
    update.message.reply_photo.assert_not_awaited()
    # Should warn user
    text_calls = [call.args[0] for call in update.message.reply_text.await_args_list]
    assert any("No OHLC data" in msg or "⚠️" in msg for msg in text_calls)
