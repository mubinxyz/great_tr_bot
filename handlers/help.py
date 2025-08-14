from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "*📌 Available Commands*\n\n"

        "*💬 General*\n"
        "`/start` — Start the bot\n"
        "`/help` — Show this help message\n\n"

        "*💲 Price*\n"
        "`/price <symbol>` — Get the current price (Price / BID / ASK)\n"
        "_Example_: `/price eurusd`\n\n"

        "*📊 Charts*\n"
        "`/chart <symbols> [timeframe=15] [outputsize=200] [from_date] [to_date]`\n"
        "- `symbols` can be a single symbol or comma-separated (e.g. `EURUSD,GBPUSD`)\n"
        "- `timeframe` accepts numbers or aliases: `1`, `5`, `15`, `60`, `1h`, `4h`, `D`, `W`, `M`.\n"
        "- If you provide two dates (from & to) the bot will force the output size for that range.\n"
        "_Examples:_\n"
        "`/chart EURUSD`\n"
        "`/chart EURUSD 60 300`\n"
        "`/chart EURUSD 60 \"2024-08-01 14:30:00\" \"2025-01-01 14:30:00\"`\n\n"

        "*🚨 Alerts*\n"
        "`/alert <symbol> <price> <timeframes>` — Create an alert and get immediate charts for the requested timeframes.\n"
        "_Example_: `/alert eurusd 1.1234 4h,15m`\n"
        "Notes:\n"
        "- Charts with your alert price are sent immediately for each timeframe.\n"
        "- If the alert condition is already met at creation, you may receive a note that it was already triggered.\n\n"

        "*📭 Manage Alerts*\n"
        "`/listalerts` — Show all your active alerts. Each alert message includes a ❌ Delete button to remove it.\n\n"

        "*🕒 Supported time tokens (examples)*\n"
        "`1m`, `5m`, `15m`, `30m`, `60` or `1h`, `4h`, `1d`, `D`, `W`, `M` — many aliases are accepted.\n\n"

        "*📝 Quick tips*\n"
        "- Symbols are case-insensitive: `eurusd`, `EUR/USD` both work.\n"
        "- Wrap multi-word dates in quotes: `\"YYYY-MM-DD HH:MM:SS\"`.\n"
        "- If a date range is provided, `outputsize` is auto-forced to cover that period.\n"
        "- Use `/listalerts` to delete alerts via the inline buttons.\n\n"

        "If you want a short example for any command, send the command here (for example: `/chart EURUSD 15`).",
        parse_mode=ParseMode.MARKDOWN
    )

# Handler instance
handler = CommandHandler("help", help_command)
