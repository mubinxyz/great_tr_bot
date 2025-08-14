import asyncio
import logging
import threading
from flask import Flask, request, abort

from telegram import Update
from telegram.ext import Application

from config import BOT_TOKEN, LOG_LEVEL, PORT, SECRET_TOKEN, WEBHOOK_URL
# WEBHOOK_URL example: "https://fa77990bc3e1.ngrok-free.app"
# SECRET_TOKEN: any string you choose; set the same in BotFather or set via setWebhook call below

from handlers import start, help, price, chart, alert
from handlers.listalerts import list_alerts_handler, delete_alert_handler
# from handlers.backtest import register_backtest_handlers
from services.db_service import init_db
from utils.alert_checker import check_alerts_job

# ----------------- Logging -----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOG_LEVEL
)
logger = logging.getLogger(__name__)

# ----------------- Flask app -----------------
app = Flask(__name__)

# Constants
WEBHOOK_PATH = "/webhook/telegram"  # Keep this in one place
# Build the full webhook URL from your public base URL + path
WEBHOOK_URL = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"

# Globals initialized in main()
application: Application | None = None  # python-telegram-bot Application
loop: asyncio.AbstractEventLoop | None = None  # background asyncio loop


def build_ptb_app() -> Application:
    """Build the PTB application and register handlers + jobs."""
    init_db()

    app_ptb = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app_ptb.add_handler(start.handler)
    app_ptb.add_handler(help.handler)
    app_ptb.add_handler(price.handler)
    app_ptb.add_handler(chart.handler)
    app_ptb.add_handler(alert.handler)
    app_ptb.add_handler(list_alerts_handler)
    app_ptb.add_handler(delete_alert_handler)
    # register_backtest_handlers(app_ptb)

    # Background job every 30s
    app_ptb.job_queue.run_repeating(check_alerts_job, interval=30, first=5)

    return app_ptb


def start_async_components():
    """Start the asyncio loop and PTB application in a background thread."""
    global loop, application

    # Create dedicated event loop in a daemon thread
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()

    # Build PTB app
    application = build_ptb_app()

    # Initialize and start PTB in the background loop
    asyncio.run_coroutine_threadsafe(application.initialize(), loop).result()
    asyncio.run_coroutine_threadsafe(application.start(), loop).result()

    # Set Telegram webhook to the exact Flask route
    asyncio.run_coroutine_threadsafe(
        application.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=SECRET_TOKEN,
            drop_pending_updates=True,
        ),
        loop
    ).result()

    logger.info("PTB application started with webhook set to %s", WEBHOOK_URL)


@app.post(WEBHOOK_PATH)
def telegram_webhook():
    """Telegram will POST updates here."""
    global application, loop
    if application is None or loop is None:
        abort(503)

    # Verify Telegram secret token header (recommended)
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if SECRET_TOKEN and header_token != SECRET_TOKEN:
        abort(403)

    data = request.get_json(silent=True, force=True)
    if not data:
        abort(400)

    # Convert to Update and hand off to PTB
    update = Update.de_json(data, application.bot)
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)

    return "OK", 200


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/")
def index():
    # Handy landing page so root hits don’t 404 during testing
    return {
        "app": "great_tr_bot",
        "webhook_url": WEBHOOK_URL,
        "webhook_path": WEBHOOK_PATH,
        "status": "running"
    }, 200


@app.post("/admin/set_webhook")
def set_webhook():
    """Optional: manually reset the webhook."""
    global application, loop
    if application is None or loop is None:
        abort(503)

    fut = asyncio.run_coroutine_threadsafe(
        application.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=SECRET_TOKEN,
            drop_pending_updates=False,
        ),
        loop
    )
    result = fut.result()
    return {"ok": result, "url": WEBHOOK_URL}, 200


def main():
    logger.info("Starting Flask + PTB webhook bot...")
    start_async_components()

    # Start Flask (use a production server in production)
    app.run(host="0.0.0.0", port=int(PORT), debug=False)


if __name__ == "__main__":
    main()
