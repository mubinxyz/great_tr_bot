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

        # safe to access dict now
        price = last_data.get("price")
        bid = last_data.get("bid")
        ask = last_data.get("ask")

        # format output nicely
        if price is not None:
            try:
                price_str = f"{float(price):.6f}"  # adjust precision as you like
            except Exception:
                price_str = str(price)
        else:
            price_str = "N/A"

        bid_str = str(bid) if bid is not None else "N/A"
        ask_str = str(ask) if ask is not None else "N/A"

        await update.message.reply_text(
            f"💹 Price for {user_input.upper()}:\n"
            f"Price: {price_str}\nBID: {bid_str}  |  ASK: {ask_str}"
        )

    except Exception as e:
        logger.exception("Error in /price handler")
        await update.message.reply_text(f"⚠️ Error fetching price: {e}")

handler = CommandHandler("price", price_command)
