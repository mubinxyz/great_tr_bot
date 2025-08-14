# services/chart_service.py

from utils.chart_utils import generate_chart_image
from utils.compute_fromdate import compute_from_date
from utils.normalize_data import normalize_timeframe
import time

def get_chart(symbol, timeframe, alert_price=None, outputsize: int = 200, from_date=None, to_date=None):
    """
    Thin wrapper to generate chart.
    """
    timeframe_normalized = normalize_timeframe(timeframe)

    if to_date is None:
        to_date = int(time.time())
    if from_date is None:
        from_date = compute_from_date(timeframe_normalized, outputsize, to_date)

    buf, period_minutes = generate_chart_image(
        symbol=symbol,
        alert_price=alert_price,
        timeframe=timeframe_normalized,
        from_date=from_date,
        to_date=to_date,
        outputsize=outputsize
    )
    return buf, period_minutes
