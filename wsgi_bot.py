import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application

from config import LOG_LEVEL, BOT_TOKEN, WEBHOOK_URL
from handlers import start, help, price, chart, alert
from handlers.listalerts import list_alerts_handler, delete_alert_handler
from services.db_service import init_db
from utils.alert_checker import check_alerts_job

# ------------------ Logging ------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

# ------------------ Initialize DB ------------------
init_db()

# ------------------ Telegram Application ------------------
application = Application.builder().token(BOT_TOKEN).build()

# Register handlers
application.add_handler(start.handler)
application.add_handler(help.handler)
application.add_handler(price.handler)
application.add_handler(chart.handler)
application.add_handler(alert.handler)
application.add_handler(list_alerts_handler)
application.add_handler(delete_alert_handler)

# ------------------ Flask App ------------------
flask_app = Flask(__name__)

@flask_app.post(f"/webhook/{BOT_TOKEN}")
async def webhook():
    """Telegram will POST updates here"""
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"

# ------------------ Startup Tasks ------------------
async def on_startup():
    """Initialize and start application, set webhook, and schedule jobs"""
    await application.initialize()
    await application.start()            # Starts bot + dispatcher + job queue

    # Set webhook URL
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set to %s", WEBHOOK_URL)

    # Start background jobs
    application.job_queue.run_repeating(check_alerts_job, interval=10, first=4)
    logger.info("Background jobs scheduled.")

# Ensure startup runs
asyncio.get_event_loop().run_until_complete(on_startup())

# ------------------ WSGI Entry Point for Passenger ------------------
app = flask_app

# ------------------ Local Testing ------------------
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000)
