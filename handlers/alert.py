# handlers/alert.py
import asyncio
from telegram.ext import CommandHandler
from services.user_service import get_or_create_user
from services.alert_service import create_alert
from utils.chart_utils import generate_chart_image
from utils.normalize_data import normalize_timeframe


async def alert_command(update, context):
    """
    /alert SYMBOL PRICE TIMEFRAMES
    Example:
      /alert eurusd 1.1234 4h,15m
    """
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /alert SYMBOL PRICE TIMEFRAMES\nExample: /alert eurusd 1.1234 4h,15m"
        )
        return

    symbol = context.args[0]
    try:
        price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid price format.")
        return

    timeframes = [s.strip() for s in context.args[2].split(",") if s.strip()]

    # Validate & normalize timeframes
    normalized_tfs = []
    for tf in timeframes:
        try:
            normalized_tfs.append(normalize_timeframe(tf))
        except ValueError as e:
            await update.message.reply_text(str(e))
            return

    # Get or create the user
    user = get_or_create_user(
        chat_id=update.effective_chat.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )

    try:
        alert = create_alert(
            user_id=user.id,
            symbol=symbol,
            target_price=price,
            timeframes=normalized_tfs
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed to create alert: {e}")
        return

    await update.message.reply_text(
        f"✅ Alert saved: {alert.symbol} {alert.direction.value} {alert.target_price} "
        f"on {alert.timeframes}\nAlert ID: {alert.id}"
    )

    # Immediately send current charts (non-blocking)
    loop = asyncio.get_running_loop()
    for tf in normalized_tfs:
        try:
            # Run the blocking chart generator in a thread
            buf, interval_norm = await loop.run_in_executor(
                None,
                generate_chart_image,
                symbol,
                tf,
                alert.target_price  # pass alert price to draw horizontal line
            )

            await update.message.reply_photo(
                photo=buf,
                filename=f"{symbol}_{interval_norm}.png",
                caption=f"⏱ Timeframe: {interval_norm}, Symbol: {symbol.upper()}"
            )

        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not generate chart for {symbol} {tf}: {e}")

    if alert.triggered:
        await update.message.reply_text("⚡️ Note: This alert condition was already met at creation time.")

handler = CommandHandler("alert", alert_command)
