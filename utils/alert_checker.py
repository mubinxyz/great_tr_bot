# utils/alert_checker.py
import asyncio
from utils.chart_utils import generate_chart_image
from utils.scrape_last_data import get_last_data
from services.alert_service import get_pending_alerts, mark_alert_triggered
from models.alert import AlertDirection

# unified data service (used for price lookups and OHLC)



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
        # common keys: 'price', maybe 'last'
        if "price" in price_resp and price_resp["price"] is not None:
            return float(price_resp["price"])
        if "last" in price_resp and price_resp["last"] is not None:
            return float(price_resp["last"])
        # try any numeric-looking value
        for k in ("close", "ask", "bid", "last_price"):
            if k in price_resp and price_resp[k] is not None:
                try:
                    return float(price_resp[k])
                except Exception:
                    pass
        return None
    # numeric-like response
    try:
        return float(price_resp)
    except Exception:
        return None


async def check_alerts_job(context):
    """
    Periodic job: checks pending alerts and triggers if conditions are met.
    Meant to be scheduled in the bot JobQueue (e.g. every 30 seconds).
    """
    alerts = get_pending_alerts()
    if not alerts:
        return  # nothing to do

    for alert in alerts:
        try:
            # get_price may return a dict or a plain number
            price_resp = get_last_data(alert.symbol)
            current_price = _extract_price(price_resp)

            if current_price is None:
                # couldn't determine price, skip this alert for now
                print(f"[AlertChecker] Could not fetch price for {alert.symbol}; skipping alert {alert.id}")
                continue

            # Compare according to alert direction
            triggered_now = False
            if alert.direction == AlertDirection.ABOVE and current_price >= float(alert.target_price):
                triggered_now = True
            elif alert.direction == AlertDirection.BELOW and current_price <= float(alert.target_price):
                triggered_now = True

            if triggered_now:
                # Mark as triggered
                mark_alert_triggered(alert.id)

                # Notify user
                # alert.user should be available (relationship); fall back to user_id if not
                chat_id = getattr(getattr(alert, "user", None), "chat_id", None) or getattr(alert, "user_id", None)
                msg_text = (
                    f"📢 Price Alert Triggered!\n"
                    f"{alert.symbol} is now {alert.direction.value} {alert.target_price}\n"
                    f"Current Price: {current_price}"
                )
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg_text)
                except Exception as e:
                    print(f"[AlertChecker] Failed to send trigger message for alert {alert.id} to {chat_id}: {e}")

                # Send charts for all timeframes in the alert (run blocking generator in executor)
                for tf in str(alert.timeframes).split(","):
                    tf = tf.strip()
                    if not tf:
                        continue
                    try:
                        loop = asyncio.get_running_loop()
                        # generate_chart_image is blocking; run in threadpool
                        buf, interval_minutes = await loop.run_in_executor(
                            None,
                            generate_chart_image,
                            alert.symbol,
                            tf,
                            alert.target_price,  # alert_price
                            None  # outputsize -> let generate_chart_image use its default
                        )

                        # send the photo (BytesIO buffer)
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=buf,
                            filename=f"{alert.symbol}_{interval_minutes}.png",
                            caption=f"⏱ Timeframe: {interval_minutes} minutes, Symbol: {alert.symbol}"
                        )

                    except Exception as e:
                        # notify user that chart generation failed for this timeframe
                        try:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ Could not generate chart for {alert.symbol} {tf}: {e}"
                            )
                        except Exception:
                            # best-effort only
                            print(f"[AlertChecker] Could not send error message for alert {alert.id}: {e}")

        except Exception as e:
            # top-level error for this alert; continue to next alert
            print(f"[AlertChecker] Error checking alert {getattr(alert, 'id', '?')}: {e}")
