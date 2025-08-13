# tests/test_alert_checker.py
import pytest
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import MagicMock
import asyncio

import utils.alert_checker as alert_checker
from models.alert import AlertDirection


class DummyBot:
    """A tiny async-capable bot mock that records messages and photos sent."""
    def __init__(self):
        self.sent_messages = []
        self.sent_photos = []

    async def send_message(self, chat_id=None, text=None, **kwargs):
        # Save message (chat_id, text) for assertions
        self.sent_messages.append((chat_id, text))

    async def send_photo(self, chat_id=None, photo=None, filename=None, caption=None, **kwargs):
        # Save photo details (chat_id, photo buffer or object, filename, caption)
        self.sent_photos.append((chat_id, photo, filename, caption))


@pytest.mark.asyncio
async def test_no_pending_alerts(monkeypatch):
    """When there are no pending alerts, nothing should be sent or marked."""
    monkeypatch.setattr(alert_checker, "get_pending_alerts", lambda: [])
    bot = DummyBot()
    ctx = SimpleNamespace(bot=bot)

    # Run the job
    await alert_checker.check_alerts_job(ctx)

    assert bot.sent_messages == []
    assert bot.sent_photos == []


@pytest.mark.asyncio
async def test_price_not_triggering(monkeypatch):
    """If current price doesn't meet alert condition, do not trigger or notify."""
    # Fake alert item
    alert = SimpleNamespace(
        id=1,
        symbol="BTCUSD",
        target_price=100.0,
        direction=AlertDirection.ABOVE,
        timeframes="1h,4h",
        user=SimpleNamespace(chat_id=12345),
    )

    monkeypatch.setattr(alert_checker, "get_pending_alerts", lambda: [alert])
    # Return a price lower than target
    monkeypatch.setattr(alert_checker.data_service, "get_price", lambda s: {"price": 90.0})

    mock_mark = MagicMock()
    monkeypatch.setattr(alert_checker, "mark_alert_triggered", mock_mark)

    bot = DummyBot()
    ctx = SimpleNamespace(bot=bot)

    await alert_checker.check_alerts_job(ctx)

    # Should not have been triggered
    mock_mark.assert_not_called()
    assert bot.sent_messages == []
    assert bot.sent_photos == []


@pytest.mark.asyncio
async def test_trigger_alert_and_send_charts(monkeypatch):
    """When an alert triggers, it should mark, notify and send charts for each timeframe."""
    alert = SimpleNamespace(
        id=2,
        symbol="BTCUSD",
        target_price=100.0,
        direction=AlertDirection.ABOVE,
        timeframes="1h,4h",
        user=SimpleNamespace(chat_id=77777),
    )

    monkeypatch.setattr(alert_checker, "get_pending_alerts", lambda: [alert])
    # Price above target -> trigger
    monkeypatch.setattr(alert_checker.data_service, "get_price", lambda s: {"price": 110.0})

    # mark_alert_triggered should be called
    mock_mark = MagicMock()
    monkeypatch.setattr(alert_checker, "mark_alert_triggered", mock_mark)

    # Mock generate_chart_image to return a BytesIO and a period
    fake_buf = BytesIO(b"PNGDATA")
    mock_gen = MagicMock(return_value=(fake_buf, 60))
    monkeypatch.setattr(alert_checker, "generate_chart_image", mock_gen)

    bot = DummyBot()
    ctx = SimpleNamespace(bot=bot)

    await alert_checker.check_alerts_job(ctx)

    # mark_alert_triggered should be called for this alert id
    mock_mark.assert_called_once_with(alert.id)

    # One notification message should be sent
    assert len(bot.sent_messages) >= 1
    chat_id, text = bot.sent_messages[0]
    assert chat_id == alert.user.chat_id
    assert "Price Alert Triggered" in text or "Price Alert Triggered!" in text

    # Two photos (for 1h and 4h) should be sent
    assert len(bot.sent_photos) == 2
    # verify generate_chart_image called twice (once per timeframe)
    assert mock_gen.call_count == 2
    # ensure send_photo was called with the returned BytesIO
    for sent in bot.sent_photos:
        sent_chat, sent_photo, filename, caption = sent
        assert sent_chat == alert.user.chat_id
        # photo should be the same object (BytesIO)
        assert sent_photo is fake_buf
        assert filename.endswith(".png")


@pytest.mark.asyncio
async def test_generate_chart_failure_sends_error_message(monkeypatch):
    """If chart generation raises, the user receives an error message for that timeframe."""
    alert = SimpleNamespace(
        id=3,
        symbol="BTCUSD",
        target_price=100.0,
        direction=AlertDirection.ABOVE,
        timeframes="1h,4h",
        user=SimpleNamespace(chat_id=55555),
    )

    monkeypatch.setattr(alert_checker, "get_pending_alerts", lambda: [alert])
    monkeypatch.setattr(alert_checker.data_service, "get_price", lambda s: {"price": 200.0})
    monkeypatch.setattr(alert_checker, "mark_alert_triggered", lambda aid: None)

    # Make generate_chart_image raise for the first timeframe and succeed for the second
    def side_effect_gen(symbol, tf, alert_price, outputsize):
        if tf == "1h":
            raise RuntimeError("boom")
        return (BytesIO(b"PNG2"), 60)

    monkeypatch.setattr(alert_checker, "generate_chart_image", MagicMock(side_effect=side_effect_gen))

    bot = DummyBot()
    ctx = SimpleNamespace(bot=bot)

    await alert_checker.check_alerts_job(ctx)

    # Should send at least one error message for the failed timeframe
    # and at least one photo for the successful timeframe
    error_messages = [t for (_cid, t) in bot.sent_messages if "Could not generate chart" in t or "Could not generate" in t or "Could not generate chart" in t]
    assert len(error_messages) >= 1

    # Should have at least one photo sent (for the timeframe that succeeded)
    assert len(bot.sent_photos) >= 1
