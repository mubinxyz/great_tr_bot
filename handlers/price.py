# handlers/price.py
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils.get_data import get_price
import logging

logger = logging.getLogger(__name__)

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price [INSTRUMENT] command."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a symbol, e.g., /price EURUSD")
        return

    user_input = context.args[0].strip()

    try:
        last_data = get_price(user_input)

        # MUST check for None before accessing keys
        if not last_data:
            await update.message.reply_text(f"❌ Could not fetch price for '{user_input.upper()}'. Try again later.")
            return

        # normalize values
        def _fmt(val):
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.6f}"
            except Exception:
                return str(val)

        # get common keys if dict
        if isinstance(last_data, dict):
            price = last_data.get("price") or last_data.get("last") or last_data.get("close") or last_data.get("last_price")
            bid = last_data.get("bid")
            ask = last_data.get("ask")
        else:
            # numeric-like
            price = last_data
            bid = None
            ask = None

        price_str = _fmt(price)
        bid_str = _fmt(bid)
        ask_str = _fmt(ask)

        await update.message.reply_text(
            f"💹 Price for {user_input.upper()}:\n"
            f"Price: {price_str}\nBID: {bid_str}  |  ASK: {ask_str}"
        )

    except Exception as e:
        logger.exception("Error in /price handler")
        await update.message.reply_text(f"⚠️ Error fetching price: {e}")

handler = CommandHandler("price", price_command)
