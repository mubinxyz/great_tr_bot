from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from services.twelvedata_service import TwelveDataService

td_service = TwelveDataService()

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price [INSTRUMENT] command."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a symbol, e.g., /price EURUSD")
        return

    user_input = context.args[0]
    try:
        price = td_service.get_price(user_input)
        if price is not None:
            await update.message.reply_text(f"💹 Price of {user_input.upper()}: {price}")
        else:
            await update.message.reply_text(f"❌ Could not fetch price for '{user_input}'. Try again later.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

handler = CommandHandler("price", price_command)
