# config.py
import os
from dotenv import load_dotenv

# Load .env if present (harmless if you’re using cPanel env vars instead)
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Required:
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Support both names: prefer PUBLIC_HOST, fallback to WEBHOOKS_URL
PUBLIC_HOST = os.getenv("PUBLIC_HOST") or os.getenv("WEBHOOKS_URL")
if not PUBLIC_HOST:
    raise ValueError("You must set either PUBLIC_HOST or WEBHOOKS_URL")

DB_PATH = os.getenv("DB_PATH", "database.db")

# Final webhook URL for Telegram
WEBHOOK_URL = f"https://{PUBLIC_HOST}/webhook/{BOT_TOKEN}"
