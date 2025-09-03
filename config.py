import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Bot token (required)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Database path (default: local SQLite file)
DB_PATH = os.environ.get("DB_PATH", "database.db")

# Logging level (default: INFO)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Cloudflared domain (required in production)
WEBHOOKS_URL = os.environ.get("WEBHOOKS_URL")
if not WEBHOOKS_URL:
    raise ValueError("WEBHOOKS_URL environment variable is required")

# Construct webhook URL
WEBHOOK_URL = f"https://{WEBHOOKS_URL}/webhook/{BOT_TOKEN}"
