# handlers/alert.py
import asyncio
import functools
import logging
from telegram.ext import CommandHandler
from telegram import Update
from services.user_service import get_or_create_user
from services.alert_service import create_alert
from services.chart_service import get_chart
from utils.normalize_data import normalize_timeframe, normalize_symbol

logger = logging.getLogger(__name__)
INTER_CHART_DELAY = 0.15  # polite pause between charts


async def alert_command(update: Update, context):
    """
    /alert SYMBOL PRICE TIMEFRAMES
    Example:
      /alert eurusd 1.1234 4h,15m

    This command:
      - creates an alert in DB (decides direction vs current market price)
      - returns charts immediately for given timeframes with an alert line
    """
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /alert SYMBOL PRICE TIMEFRAMES\nExample: /alert eurusd 1.2345 4h,15m"
        )
        return

    symbol = context.args[0].strip()
    price_raw = context.args[1].strip()
    tfs_raw = context.args[2].strip()

    # parse price
    try:
        price = float(price_raw)
    except Exception:
        await update.message.reply_text("⚠️ Invalid price format. Use something like: 1.2345")
        return

    # parse/normalize timeframes
    tfs_list = [s.strip() for s in tfs_raw.split(",") if s.strip()]
    if not tfs_list:
        await update.message.reply_text("⚠️ No valid timeframes provided.")
        return

    normalized_tfs = []
    for tf in tfs_list:
        try:
            normalized_tfs.append(normalize_timeframe(tf))
        except Exception as e:
            await update.message.reply_text(f"⚠️ Invalid timeframe '{tf}': {e}")
            return

    loop = asyncio.get_running_loop()

    # 1) Ensure user exists (DB likely blocking) -> run in executor
    try:
        call_user = functools.partial(
            get_or_create_user,
            chat_id=update.effective_chat.id,
            username=(update.effective_user.username if update.effective_user else None),
            first_name=(update.effective_user.first_name if update.effective_user else None),
            last_name=(update.effective_user.last_name if update.effective_user else None),
        )
        user = await loop.run_in_executor(None, call_user)
    except Exception as e:
        logger.exception("Failed to get/create user")
        await update.message.reply_text(f"⚠️ Failed to access user record: {e}")
        return

    # 2) Create alert (blocking DB call) in executor
    try:
        norm_symbol = normalize_symbol(symbol)

        call_alert = functools.partial(
            create_alert,
            user_id=user.id,
            symbol=norm_symbol,
            target_price=price,
            timeframes=normalized_tfs,
        )
        alert = await loop.run_in_executor(None, call_alert)
    except Exception as e:
        logger.exception("Failed to create alert")
        await update.message.reply_text(f"⚠️ Failed to create alert: {e}")
        return

    # Respond with confirmation
    try:
        tf_display = alert.timeframes if hasattr(alert, "timeframes") else ",".join(normalized_tfs)
        direction = getattr(alert.direction, "value", str(alert.direction))
        await update.message.reply_text(
            f"✅ Alert saved: {alert.symbol} {direction} {alert.target_price} on {tf_display}\nAlert ID: {alert.id}"
        )
    except Exception:
        # fallback minimal confirmation if SQL object shape differs
        await update.message.reply_text(f"✅ Alert saved (ID unknown).")

    # 3) Send immediate charts for each timeframe using get_chart (which computes from_date)
    norm_symbol = normalize_symbol(symbol)
    for tf in normalized_tfs:
        try:
            # debug record
            logger.debug(
                "Alert chart request: symbol=%s timeframe=%s alert_price=%s outputsize=%s",
                norm_symbol, tf, alert.target_price, 150
            )

            call_plot = functools.partial(
                get_chart,
                symbol=norm_symbol,
                timeframe=tf,
                alert_price=alert.target_price,
                outputsize=150,
                from_date=None,
                to_date=None
            )
            buf, interval_norm = await loop.run_in_executor(None, call_plot)

            # ensure buffer readable from start
            try:
                buf.seek(0)
            except Exception:
                pass

            await update.message.reply_photo(
                photo=buf,
                filename=f"{symbol}_{interval_norm}.png",
                caption=f"⏱ Timeframe: {interval_norm}, Symbol: {symbol.upper()}"
            )
        except Exception as e:
            logger.exception("Chart generation error")
            await update.message.reply_text(f"⚠️ Could not generate chart for {symbol} {tf}: {e}")

        await asyncio.sleep(INTER_CHART_DELAY)

    # 4) If alert already triggered on creation, notify user
    try:
        if getattr(alert, "triggered", False):
            await update.message.reply_text("⚡️ Note: This alert condition was already met at creation time.")
    except Exception:
        # ignore any reflection errors
        pass


handler = CommandHandler("alert", alert_command)
