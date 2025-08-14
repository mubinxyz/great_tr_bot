# utils/compute_fromdate.py
import time

# Map LiteFinance timeframes to minutes
TIMEFRAME_TO_MINUTES = {
    "1": 1,
    "5": 5,
    "15": 15,
    "30": 30,
    "60": 60,
    "240": 240,
    "D": 1440,    # 1 day
    "W": 10080,   # 1 week
    "M": 43200,   # 30 days
}

def compute_from_date(timeframe: str, outputsize: int = 200, to_date: int = None) -> int:
    """
    Compute from_date (Unix timestamp in seconds) based on timeframe and outputsize.
    
    Args:
        timeframe: LiteFinance timeframe string ('1', '15', 'D', etc.)
        outputsize: number of candles to fetch
        to_date: end timestamp (seconds). Defaults to current time.
    
    Returns:
        int: from_date timestamp in seconds
    """
    if to_date is None:
        to_date = int(time.time())

    minutes = TIMEFRAME_TO_MINUTES.get(str(timeframe), 15)
    return to_date - outputsize * minutes * 60
