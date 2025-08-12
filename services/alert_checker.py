# services/alert_checker.py
import asyncio
from services.alert_service import get_pending_alerts, mark_alert_triggered
from services.chart_service import generate_chart_image
from services.twelvedata_service import TwelveDataService
from models.alert import AlertDirection

td_service = TwelveDataService()

async def check_alerts_job(context):
    """
    Periodic job: checks pending alerts and triggers if conditions are met.
    Runs every 30 seconds (configured in bot.py JobQueue).
    """
    alerts = get_pending_alerts()
    if not alerts:
        return  # no alerts to check

    for alert in alerts:
        try:
            current_price = td_service.get_price(alert.symbol)

            if (
                alert.direction == AlertDirection.ABOVE and current_price >= alert.target_price
            ) or (
                alert.direction == AlertDirection.BELOW and current_price <= alert.target_price
            ):
                # Mark as triggered
                mark_alert_triggered(alert.id)

                # Notify user
                chat_id = alert.user.chat_id
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"📢 Price Alert Triggered!\n"
                        f"{alert.symbol} is now {alert.direction.value} {alert.target_price}\n"
                        f"Current Price: {current_price}"
                    )
                )

                # Send charts for all timeframes in alert (run blocking generator in executor)
                for tf in alert.timeframes.split(","):
                    try:
                        loop = asyncio.get_running_loop()
                        buf, interval_norm = await loop.run_in_executor(
                            None,
                            generate_chart_image,
                            alert.symbol,
                            tf,
                            alert.target_price
                        )
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=buf,
                            filename=f"{alert.symbol}_{interval_norm}.png",
                            caption=f"⏱ Timeframe: {interval_norm}, Symbol: {alert.symbol}"
                        )
                    except Exception as e:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Could not generate chart for {alert.symbol} {tf}: {e}"
                        )

        except Exception as e:
            # log error somewhere (console for now)
            print(f"[AlertChecker] Error checking alert {alert.id}: {e}")
