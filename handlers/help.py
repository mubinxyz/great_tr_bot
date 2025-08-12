from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode  # import ParseMode

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "📌 *Available Commands:*\n\n"
        "💬 *General*\n"
        "/start – Start the bot\n"
        "/help – Show this help message\n\n"
        "💲 *Price*\n"
        "/price <symbol> – Get the current price\n"
        "Example: `/price eurusd`\n\n"
        "📊 *Charts*\n"
        "/chart <symbol> <intervals> – Show a candlestick chart\n"
        "Example: `/chart eurusd 1h`\n\n"
        "🚨 *Alerts*\n"
        "/alert <symbol> <price> <interval>  – Set a price alert\n"
        "Example: `/alert 1.0850 eurusd 1h,5m `\n"
        "/listalerts – Show all your active alerts\n\n"
        "🕒 *Supported Intervals*\n"
        "1m, 5m, 15m, 30m, 1h, 4h, 1d\n\n"
        "💡 *Tips:*\n"
        "- Symbols can be `EURUSD` or `eur/usd`\n"
        "- Charts show a horizontal line for your alert price"
        "- Charts show vertical lines for seperating days",
        parse_mode="Markdown"
    )

# Handler instance
handler = CommandHandler("help", help_command)
