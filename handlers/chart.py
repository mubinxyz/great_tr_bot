import io
import asyncio
from telegram import Update, InputFile
from telegram.ext import CommandHandler, ContextTypes
import mplfinance as mpf
import pandas as pd
from services.twelvedata_service import TwelveDataService

td_service = TwelveDataService()

print("=== handlers.chart.py loaded ===")
def normalize_interval(tf: str) -> str:
    tf = tf.lower().strip()

    # Supported canonical intervals (match TwelveData)
    supported = {
        "1min", "5min", "15min", "30min", "45min",
        "1h", "2h", "3h", "4h", "6h", "8h",
        "1day", "1week", "1month"
    }

    # If already canonical, return as-is
    if tf in supported:
        return tf

    # Map common shorthand / alternative inputs into canonical intervals
    mapping = {
        "1": "1min", "1m": "1min", "1min": "1min",
        "5": "5min", "5m": "5min", "5min": "5min",
        "15": "15min", "15m": "15min", "15min": "15min",
        "30": "30min", "30m": "30min", "30min": "30min",
        "45": "45min", "45m": "45min", "45min": "45min",
        "1h": "1h", "2h": "2h", "3h": "3h", "4h": "4h",
        "6h": "6h", "8h": "8h",
        "1d": "1day", "day": "1day", "1day": "1day",
        "1w": "1week", "1week": "1week",
        "1mo": "1month", "month": "1month", "1month": "1month",
    }

    if tf in mapping:
        return mapping[tf]

    raise ValueError(f"Invalid timeframe: {tf}")

# Updated generate_and_send_chart without volume:
async def generate_and_send_chart(update, symbol, interval):
    try:
        interval_norm = normalize_interval(interval)
        candles = td_service.get_ohlc(symbol, interval_norm, outputsize=200)

        import pandas as pd
        import mplfinance as mpf
        import io

        df = pd.DataFrame(candles)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)

        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])

        buf = io.BytesIO()
        mpf.plot(
            df,
            type='candle',
            style='yahoo',
            figsize=(16, 9),
            tight_layout=True,
            savefig=dict(fname=buf, dpi=100)
            # Removed volume=True to disable volume subplot
        )
        buf.seek(0)
        await update.message.reply_photo(
            photo=buf,
            filename=f"{symbol}_{interval_norm}.png",
            caption=f"⏱ Timeframe: {interval_norm}, Symbol: {symbol}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed to generate chart for {symbol} {interval}: {e}")

# Updated chart_command to catch invalid interval early:
async def chart_command(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /chart SYMBOL TIMEFRAMES\nExample: /chart eurusd 4h,15")
        return

    symbol = context.args[0]
    timeframes = context.args[1].split(',')

    for tf in timeframes:
        try:
            tf_norm = normalize_interval(tf.strip())
        except ValueError as e:
            await update.message.reply_text(str(e))
            continue

        await generate_and_send_chart(update, symbol, tf_norm)

handler = CommandHandler("chart", chart_command)