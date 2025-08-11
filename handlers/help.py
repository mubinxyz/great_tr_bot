from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "📌 Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "Just type anything and I’ll echo it back!"
    )

# Handler instance
handler = CommandHandler("help", help_command)
