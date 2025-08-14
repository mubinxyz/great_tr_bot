# bot.py
import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application
<<<<<<< HEAD
from config import LOG_LEVEL, BOT_TOKEN
from handlers import start, help, price, chart, alert
=======
from config import BOT_TOKEN, LOG_LEVEL, WEBHOOK_URL
from handlers import start, help, price, chart, alert, listalerts
>>>>>>> bcaf71997d2e1da064187f918f80e55ac945132f
from services.db_service import init_db
from utils.alert_checker import check_alerts_job

# ----- Logging -----
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# ----- Flask app -----
app = Flask(__name__)

# ----- DB Init -----
init_db()

# ----- Telegram Application -----
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Add handlers
telegram_app.add_handler(start.handler)
telegram_app.add_handler(help.handler)
telegram_app.add_handler(price.handler)
telegram_app.add_handler(chart.handler)
telegram_app.add_handler(alert.handler)
telegram_app.add_handler(listalerts.handler)

# Start jobs
telegram_app.job_queue.run_repeating(check_alerts_job, interval=25, first=5)

# ----- Initialize application (required for WSGI) -----
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(telegram_app.initialize())

# ----- Routes -----
@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook/telegram', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        loop.run_until_complete(telegram_app.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.exception("Error in webhook")
        return "Error", 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        loop.run_until_complete(telegram_app.bot.delete_webhook())
        loop.run_until_complete(telegram_app.bot.set_webhook(url=WEBHOOK_URL + "/telegram"))
        return "Webhook set successfully"
    except Exception as e:
        logger.exception("Error setting webhook")
        return f"Error: {e}", 500
