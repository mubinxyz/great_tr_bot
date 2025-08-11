from telegram import Update
from telegram.ext import MessageHandler, ContextTypes, filters

async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echoes the received message."""
    await update.message.reply_text(update.message.text)

# Handler instance
handler = MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message)
