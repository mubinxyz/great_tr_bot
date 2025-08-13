# services/chart_service.py

from utils.chart_utils import generate_chart_image, DEFAULT_OUTPUTSIZE
from utils.get_data import DataService

data_service = DataService()
DEFAULT_OUTPUTSIZE = DEFAULT_OUTPUTSIZE

def get_chart(symbol: str, interval: str, alert_price: float = None, outputsize: int = None):
    """
    Fetches OHLC data and generates a candlestick chart image.
    This is the function the bot should call for /chart commands.
    """
    if outputsize is None:
        outputsize = DEFAULT_OUTPUTSIZE
    buf, period_minutes = generate_chart_image(symbol, interval, alert_price, outputsize)
    return buf, period_minutes