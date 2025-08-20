# bot.py

import logging
from telegram.ext import Application
from config import LOG_LEVEL, BOT_TOKEN
from handlers import start, help, price, chart, alert
from services.db_service import init_db
from utils.alert_checker import check_alerts_job
from handlers.listalerts import list_alerts_handler, delete_alert_handler
# from handlers.backtest import register_backtest_handlers

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
    application.add_handler(price.handler)
    application.add_handler(chart.handler)
    application.add_handler(alert.handler)
    application.add_handler(list_alerts_handler)
    application.add_handler(delete_alert_handler)
    # register_backtest_handlers(application)

    # Add background job every 30 seconds
    application.job_queue.run_repeating(check_alerts_job, interval=10, first=4)

    # Start polling
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
