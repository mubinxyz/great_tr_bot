# utils/alert_checker.py
import asyncio
import functools
import logging
from utils.chart_utils import generate_chart_image
from utils.get_data import get_price
from services.alert_service import get_pending_alerts, mark_alert_triggered
from models.alert import AlertDirection

logger = logging.getLogger(__name__)


def _extract_price(price_resp):
    """
    Helper to extract a numeric price from DataService.get_price return value.
    Accepts either:
      - a dict like {"price": 123.45, ...}
      - a plain numeric (float/int)
      - None -> returns None
    """
    if price_resp is None:
        return None

    if isinstance(price_resp, dict):
        # check common keys first
        for key in ("price", "last", "close", "ask", "bid", "last_price"):
            if key in price_resp and price_resp[key] is not None:
                try:
                    return float(price_resp[key])
                except (ValueError, TypeError):
                    continue
        # fallback: scan values for numeric-like
        for v in price_resp.values():
            try:
                return float(v)
            except Exception:
                continue
        return None

    # numeric-like
    try:
        return float(price_resp)
    except Exception:
        return None


async def check_alerts_job(context):
    """
    Periodic job: checks pending alerts and triggers if conditions are met.
    Intended to be scheduled in bot job queue (e.g. every 30s).
    """
    try:
        alerts = get_pending_alerts()
    except Exception as e:
        logger.exception("Failed to load pending alerts: %s", e)
        return

    if not alerts:
        return

    loop = asyncio.get_running_loop()

    for alert in alerts:
        try:
            # 1) fetch current price in executor (get_price is blocking)
            try:
                price_resp = await loop.run_in_executor(None, functools.partial(get_price, alert.symbol))
            except Exception as e:
                logger.warning("[AlertChecker] Price fetch failed for %s (alert %s): %s", alert.symbol, getattr(alert, "id", "?"), e)
                continue

            current_price = _extract_price(price_resp)
            if current_price is None:
                logger.warning("[AlertChecker] Could not parse price for %s (alert %s); skipping", alert.symbol, getattr(alert, "id", "?"))
                continue

            # 2) evaluate trigger condition based on direction
            triggered_now = False
            try:
                if alert.direction == AlertDirection.ABOVE and current_price >= float(alert.target_price):
                    triggered_now = True
                elif alert.direction == AlertDirection.BELOW and current_price <= float(alert.target_price):
                    triggered_now = True
            except Exception as e:
                logger.exception("[AlertChecker] Error comparing prices for alert %s: %s", getattr(alert, "id", "?"), e)
                continue

            if not triggered_now:
                continue

            # 3) mark alert triggered in DB (blocking -> executor)
            try:
                updated_alert = await loop.run_in_executor(None, functools.partial(mark_alert_triggered, alert.id))
            except Exception as e:
                logger.exception("[AlertChecker] Failed to mark alert %s as triggered: %s", getattr(alert, "id", "?"), e)
                # still attempt to notify user (best-effort) below
                updated_alert = alert

            # 4) notify user
            # Resolve chat id: prefer related user.chat_id if relationship exists; otherwise use user_id
            user_obj = getattr(updated_alert, "user", None)
            chat_id = None
            if user_obj is not None:
                chat_id = getattr(user_obj, "chat_id", None)
            if not chat_id:
                chat_id = getattr(updated_alert, "user_id", None)

            msg_text = (
                f"📢 Price Alert Triggered!\n"
                f"{updated_alert.symbol} is now {updated_alert.direction.value} {updated_alert.target_price}\n"
                f"Current Price: {current_price}"
            )

            try:
                await context.bot.send_message(chat_id=chat_id, text=msg_text)
            except Exception as e:
                logger.exception("[AlertChecker] Failed to send trigger message for alert %s to %s: %s", getattr(updated_alert, "id", "?"), chat_id, e)

            # 5) send charts for all timeframes in alert (blocking plotting -> executor)
            tfs = str(updated_alert.timeframes or "").split(",")
            for tf in tfs:
                tf = tf.strip()
                if not tf:
                    continue
                try:
                    call_plot = functools.partial(
                        generate_chart_image,
                        symbol=updated_alert.symbol,
                        alert_price=updated_alert.target_price,
                        timeframe=tf,
                        from_date=None,
                        to_date=None,
                        outputsize=None
                    )
                    buf, interval_minutes = await loop.run_in_executor(None, call_plot)

                    # ensure buffer is rewound
                    try:
                        buf.seek(0)
                    except Exception:
                        pass

                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=buf,
                        filename=f"{updated_alert.symbol}_{interval_minutes}.png",
                        caption=f"⏱ Timeframe: {interval_minutes}, Symbol: {updated_alert.symbol}"
                    )
                except Exception as e:
                    logger.exception("[AlertChecker] Failed to generate/send chart for alert %s tf=%s: %s", getattr(updated_alert, "id", "?"), tf, e)
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not generate chart for {updated_alert.symbol} {tf}: {e}")
                    except Exception:
                        logger.exception("[AlertChecker] Also failed to notify user about chart generation error for alert %s", getattr(updated_alert, "id", "?"))

        except Exception as e:
            logger.exception("[AlertChecker] Unexpected error when processing alert %s: %s", getattr(alert, "id", "?"), e)
