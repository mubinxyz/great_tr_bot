# config.py
import os
import logging
from dotenv import load_dotenv

# If you use a .env file in dev, this will load it.
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_PATH = os.environ.get("DB_PATH", "database.db")

# LOG_LEVEL: support both numeric and string ("DEBUG"/"INFO")
_raw_log = os.environ.get("LOG_LEVEL", "INFO")
try:
    LOG_LEVEL = int(_raw_log)
except ValueError:
    LOG_LEVEL = getattr(logging, _raw_log.upper(), logging.INFO)

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", 8000))

# SECRET_TOKEN for Telegram webhook verification (recommended)
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "")

# Optional: TwelveData keys (leave blank or set envs individually)
TD_API_KEY_1 = os.environ.get("TD_API_KEY_1", "")
# ... add other keys as needed
