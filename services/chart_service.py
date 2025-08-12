# services/chart_service.py
import matplotlib
matplotlib.use("Agg")   # must come before mplfinance/pyplot imports

import io
from io import BytesIO
import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from datetime import time
from services.twelvedata_service import TwelveDataService

td_service = TwelveDataService()

DEFAULT_OUTPUTSIZE = 200  # keep same default as you used elsewhere

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

def generate_chart_image(symbol: str, interval: str, alert_price: float = None, outputsize: int = None):
    """
    Returns: (buf: BytesIO, interval_norm: str)

    Uses mpf.make_addplot for horizontal alert line and 'alines' param
    for vertical day separators (first bar of each day). Very similar to
    the working snippet your friend used.
    """
    if outputsize is None:
        outputsize = DEFAULT_OUTPUTSIZE * 2  # follow friend's 'double' heuristic

    interval_norm = normalize_interval(interval)

    # fetch candles
    candles = td_service.get_ohlc(symbol, interval_norm, outputsize=outputsize)
    df = pd.DataFrame(candles)
    if df.empty:
        raise ValueError("No OHLC data returned")

    # ensure index and types
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)

    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Prepare addplot for alert horizontal line (aligned Series)
    add_plots = []
    if alert_price is not None:
        alert_price = float(alert_price)
        # create a Series indexed like df so mpf lines align with x-axis
        alert_series = pd.Series([alert_price] * len(df), index=df.index)
        add_plots.append(
            mpf.make_addplot(
                alert_series,
                type='line',
                panel=0,
                color='red',        # red alert line for contrast
                linestyle='--',
                width=1.2,
                alpha=0.9
            )
        )

    # --- compute day-first timestamps (first available bar for each calendar day) ---
    day_firsts_series = df.index.to_series().groupby(df.index.date).first()

    # Robust conversion to python datetimes (use np.array to keep old behavior)
    if hasattr(day_firsts_series, "dt"):
        day_firsts = list(np.array(day_firsts_series.dt.to_pydatetime()))
    else:
        day_firsts = [pd.Timestamp(x).to_pydatetime() for x in day_firsts_series]

    # Bound check: keep only day_firsts that fall within the df index range (inclusive)
    idx_min = df.index[0]
    idx_max = df.index[-1]
    day_firsts = [d for d in day_firsts if d >= idx_min and d <= idx_max]

    # If there are day-firsts, create vertical line segments from ymin to ymax at each day start
    alines_dict = None
    if day_firsts:
        y_min = float(df['low'].min())
        y_max = float(df['high'].max())

        # include alert_price in span so vlines cover entire visible range
        if alert_price is not None:
            y_min = min(y_min, alert_price)
            y_max = max(y_max, alert_price)

        vertical_lines = [
            ((pd.Timestamp(day).to_pydatetime(), y_min), (pd.Timestamp(day).to_pydatetime(), y_max))
            for day in day_firsts
        ]
        alines_dict = dict(
            alines=vertical_lines,
            colors=['#1f77b4'] * len(vertical_lines),
            linestyle=[':'] * len(vertical_lines),
            linewidths=[0.9] * len(vertical_lines),
            alpha=0.9
        )

    # Plot with mplfinance (use 'data' key, not passing df as positional)
    buf = BytesIO()

    plot_kwargs = dict(
        data=df,
        type='candle',
        style='charles',
        addplot=add_plots if add_plots else None,
        volume=False,
        figratio=(16, 9),
        figscale=1.15,
        savefig=dict(fname=buf, dpi=150, bbox_inches='tight'),
    )

    if alines_dict:
        plot_kwargs['alines'] = alines_dict

    # Remove addplot if it's empty to avoid validator complaining
    if plot_kwargs.get('addplot') is None:
        plot_kwargs.pop('addplot')

    # Call mplfinance plot (this will write image into our BytesIO via savefig)
    mpf.plot(**plot_kwargs)

    # close matplotlib figures
    plt.close('all')

    buf.seek(0)
    return buf, interval_norm
