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
TD_API_KEYS = [
    os.getenv("TD_API_KEY_1"),
    os.getenv("TD_API_KEY_2"),
    os.getenv("TD_API_KEY_3"),
    os.getenv("TD_API_KEY_4"),
    os.getenv("TD_API_KEY_5"),
    os.getenv("TD_API_KEY_6"),
    os.getenv("TD_API_KEY_7"),
    os.getenv("TD_API_KEY_8"),
    
]
TD_API_KEYS = [key for key in TD_API_KEYS if key]

TD_STRATEGY_API_KEYS = [
    os.getenv('TD_STRATEGY_API_KEY_1')
]

# ===== Validations =====
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in .env file!")
if not TD_API_KEYS:
    raise ValueError("At least one TwelveData API key must be set in .env!")
