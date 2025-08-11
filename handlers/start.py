from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text(
        "👋 Hello! I’m your bot.\n\n"
        "Use /help to see what I can do."
    )

# Handler instance to register in bot.py
handler = CommandHandler("start", start_command)
