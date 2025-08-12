from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "*📌 Available Commands:*\n\n"
        
        "*💬 General*\n"
        "`/start` – Start the bot\n"
        "`/help` – Show this help message\n\n"
        
        "*💲 Price*\n"
        "`/price <symbol>` – Get the current price\n"
        "_Example_: `/price eurusd`\n\n"
        
        "*📊 Charts*\n"
        "`/chart <symbol> <interval>` – Show a candlestick chart\n"
        "_Example_: `/chart eurusd 1h`\n\n"
        
        "*🚨 Alerts*\n"
        "`/alert <price> <symbol> <interval>` – Set a price alert\n"
        "_Example_: `/alert 1.0850 eurusd 1h,5m`\n"
        "`/listalerts` – Show all your active alerts\n\n"
        
        "*🕒 Supported Intervals*\n"
        "`1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`\n\n"
        
        "*💡 Tips:*\n"
        "- Symbols can be `EURUSD` or `eur/usd`\n"
        "- Charts show a horizontal line for your alert price\n"
        "- Charts show vertical lines for separating days\n\n"
        
        "*🔁 /backtest – Run a trading strategy backtest*\n"
        "You’ll be guided through selecting a category and entering parameters.\n\n"
        
        "*Parameter Formats:*\n"
        "`SYMBOL FAST,SLOW MA_TYPE TIMEFRAME`\n"
        "_Example_: `/backtest EURUSD 10,50 ssma 1h`\n\n"
        "`SYMBOL FAST SLOW MA_TYPE TIMEFRAME`\n"
        "_Example_: `/backtest eur/usd 10 50 ema 4h`\n\n"
        
        "*Notes:*\n"
        "- `SYMBOL`: e.g. `EURUSD`, `eur/usd`\n"
        "- `FAST`, `SLOW`: moving average periods\n"
        "- `MA_TYPE`: `ssma` | `sma` | `ema`\n"
        "- `TIMEFRAME`: `1min` | `5min` | `15min` | `1h` | `4h` | `1day`\n"
        "- HTML report is auto-deleted after sending\n\n"
        
        "*Example Flow:*\n"
        "1. `/backtest` → choose category → choose strategy\n"
        "2. Send params like: `EURUSD 10,50 ema 1h`\n"
        "3. Receive stats + performance chart",
        parse_mode=ParseMode.MARKDOWN
    )

# Handler instance
handler = CommandHandler("help", help_command)
