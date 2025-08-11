# services/chart_service.py
import io
import pandas as pd
import mplfinance as mpf
from services.twelvedata_service import TwelveDataService
from datetime import time

td_service = TwelveDataService()

def normalize_interval(tf: str) -> str:
    tf = tf.lower().strip()
    supported = {
        "1min", "5min", "15min", "30min", "45min",
        "1h", "2h", "3h", "4h", "6h", "8h",
        "1day", "1week", "1month"
    }
    if tf in supported:
        return tf

    mapping = {
        "1": "1min", "1m": "1min", "1min": "1min",
        "5": "5min", "5m": "5min", "5min": "5min",
        "15": "15min", "15m": "15min", "15min": "15min",
        "30": "30min", "30m": "30min", "30min": "30min",
        "45": "45min", "45m": "45min", "45min": "45min",
        "1h": "1h", "2h": "2h", "3h": "3h", "4h": "4h",
        "6h": "6h", "8h": "8h",
        "1d": "1day", "day": "1day", "1day": "1day",
        "1w": "1week", "1week": "1week",
        "1mo": "1month", "month": "1month", "1month": "1month",
    }
    if tf in mapping:
        return mapping[tf]

    raise ValueError(f"Invalid timeframe: {tf}")

def generate_chart_image(symbol: str, interval: str, alert_price: float = None):
    """
    Returns: (buf: BytesIO, interval_norm: str)
    """
    interval_norm = normalize_interval(interval)
    candles = td_service.get_ohlc(symbol, interval_norm, outputsize=200)

    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)

    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col])

    # Vertical day separators (midnight timestamps)
    vlines = [ts for ts in df.index if ts.time() == time(0, 0)]

    buf = io.BytesIO()

    plot_kwargs = dict(
        type='candle',
        style='yahoo',
        figsize=(16, 9),
        tight_layout=True,
        vlines=dict(vlines=vlines, linewidths=1.5, alpha=0.8, linestyle=':'),
        hlines=dict(hlines=[alert_price] if alert_price is not None else [], colors=['red'], linestyle='-'),
        savefig=dict(fname=buf, dpi=100)
    )

    # mpf.plot expects df as first positional arg
    mpf.plot(df, **plot_kwargs)

    buf.seek(0)
    return buf, interval_norm
