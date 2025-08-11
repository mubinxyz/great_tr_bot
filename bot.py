import logging
from telegram.ext import Application
from config import BOT_TOKEN, LOG_LEVEL
from handlers import start, help, echo, price, chart
from services.db_service import init_db

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

def main():
    """Start the bot."""
    init_db()  # Create tables if not exist
    
    # Create the application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(start.handler)
    application.add_handler(help.handler)
    application.add_handler(echo.handler)
    application.add_handler(price.handler)
    application.add_handler(chart.handler)

    # Start polling
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
