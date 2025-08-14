import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Telegram Bot Config
BOT_TOKEN = os.getenv("BOT_TOKEN")

# SQLite Database Path (defaults to database.db if not provided)
DB_PATH = os.getenv("DB_PATH", "database.db")

# Logging Config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# TwelveData API Keys (remove None values)


# ===== Validations =====
# if not BOT_TOKEN:
#     raise ValueError("BOT_TOKEN is missing in .env file!")
# if not TD_API_KEYS:
#     raise ValueError("At least one TwelveData API key must be set in .env!")
