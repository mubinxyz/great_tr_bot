from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from services.user_service import get_or_create_user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(
        chat_id=update.message.chat.id,
        username=update.message.from_user.username,
        first_name=update.message.from_user.first_name,
        last_name=update.message.from_user.last_name
    )
    
    """Handles the /start command."""
    await update.message.reply_text(
        "👋 Hello! I’m your bot.\n\n"
        "Use /help to see what I can do."
    )

# Handler instance to register in bot.py
handler = CommandHandler("start", start_command)
