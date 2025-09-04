# wsgi_bot.py
import logging
import asyncio
import threading
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

# ------------------ Telegram Application (no start here) ------------------
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

@flask_app.get("/health")
def health():
    return "ok"
    
    
# We'll forward updates to the bot loop (do not await here)
@flask_app.post(f"/webhook/{BOT_TOKEN}")
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    # Submit processing to the bot's event loop (see start_bot below)
    try:
        future = asyncio.run_coroutine_threadsafe(application.process_update(update), bot_loop)
        # optional: attach callback to log exceptions from processing
        def _done_callback(f):
            try:
                f.result()
            except Exception:
                logger.exception("Exception while processing update in bot loop")
        future.add_done_callback(_done_callback)
    except Exception:
        logger.exception("Failed to schedule update on bot loop")
    return "ok"

# ------------------ Startup Tasks (to be executed inside bot loop) ------------------
async def on_startup():
    """Initialize and start application, set webhook, and schedule jobs"""
    await application.initialize()
    await application.start()            # Starts bot + dispatcher + job queue

    # Set webhook URL
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set to %s", WEBHOOK_URL)

    # Start background jobs (runs in the bot's job queue)
    application.job_queue.run_repeating(check_alerts_job, interval=10, first=4)
    logger.info("Background jobs scheduled.")

# ------------------ Run the bot in a dedicated thread + loop ------------------
bot_loop = asyncio.new_event_loop()

def _start_bot_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(on_startup())
    logger.info("Bot loop started and running forever")
    loop.run_forever()

bot_thread = threading.Thread(target=_start_bot_loop, args=(bot_loop,), daemon=True)
bot_thread.start()

# ------------------ WSGI Entry Point for Passenger ------------------
app = flask_app

# ------------------ Local Testing ------------------
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000)
