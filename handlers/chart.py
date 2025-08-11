from telegram.ext import CommandHandler
from services.chart_service import normalize_interval, generate_chart_image

async def chart_command(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /chart SYMBOL TIMEFRAMES\nExample: /chart eurusd 4h,15")
        return

    symbol = context.args[0]
    timeframes = context.args[1].split(',')

    for tf in timeframes:
        try:
            buf, interval_norm = generate_chart_image(symbol, tf.strip())
            await update.message.reply_photo(
                photo=buf,
                filename=f"{symbol}_{interval_norm}.png",
                caption=f"⏱ Timeframe: {interval_norm}, Symbol: {symbol}"
            )
        except ValueError as e:
            await update.message.reply_text(str(e))
        except Exception as e:
            await update.message.reply_text(f"⚠️ Failed to generate chart for {symbol} {tf}: {e}")

handler = CommandHandler("chart", chart_command)
