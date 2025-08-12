# handlers/chart.py
import asyncio
from telegram.ext import CommandHandler
from telegram import Update
from services.chart_service import normalize_interval, generate_chart_image

# tweakable small delay between chart requests to avoid bursts
INTER_CHART_DELAY = 0.25  # seconds

async def chart_command(update: Update, context):
    """
    Usage:
      /chart <symbols> <timeframes>
    Example:
      /chart eurusd,gbpusd 4h,15m
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /chart <symbols> <timeframes>\nExample: /chart eurusd,gbpusd 4h,15m"
        )
        return

    raw_symbols = context.args[0]
    raw_timeframes = context.args[1]

    symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
    if not symbols:
        await update.message.reply_text("⚠️ No valid symbols provided.")
        return

    raw_tfs = [t.strip() for t in raw_timeframes.split(",") if t.strip()]
    if not raw_tfs:
        await update.message.reply_text("⚠️ No valid timeframes provided.")
        return

    # Validate & normalize timeframes up-front
    normalized_tfs = []
    for tf in raw_tfs:
        try:
            normalized_tfs.append(normalize_interval(tf))
        except ValueError as e:
            await update.message.reply_text(f"⚠️ Invalid timeframe '{tf}': {e}")
            return

    await update.message.reply_text(
        f"Generating charts for {len(symbols)} symbol(s) × {len(normalized_tfs)} timeframe(s). This may take a moment..."
    )

    loop = asyncio.get_running_loop()

    for symbol in symbols:
        for tf in normalized_tfs:
            try:
                # generate_chart_image is blocking -> run in threadpool
                buf, interval_norm = await loop.run_in_executor(
                    None, generate_chart_image, symbol, tf, None
                )

                await update.message.reply_photo(
                    photo=buf,
                    filename=f"{symbol}_{interval_norm}.png",
                    caption=f"⏱ Timeframe: {interval_norm}, Symbol: {symbol.upper()}"
                )

            except Exception as e:
                # per-chart error (keeps other charts running)
                await update.message.reply_text(f"⚠️ Failed to generate chart for {symbol} {tf}: {e}")

            await asyncio.sleep(INTER_CHART_DELAY)

handler = CommandHandler("chart", chart_command)
