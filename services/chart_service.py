# services/chart_service.py
import matplotlib
matplotlib.use("Agg")   # must be set BEFORE importing mplfinance/pyplot

from io import BytesIO
import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from services.twelvedata_service import TwelveDataService

td_service = TwelveDataService()
DEFAULT_OUTPUTSIZE = 200

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
    Returns (BytesIO buffer, normalized_interval)
    Pure mplfinance plotting using 'yahoo' base style but with reduced font sizes.
    - addplot for horizontal alert line (aligned Series)
    - alines for vertical day separators (first bar of each day)
    - save PNG into BytesIO and return (buf, interval_norm)
    """
    if outputsize is None:
        outputsize = DEFAULT_OUTPUTSIZE * 2

    interval_norm = normalize_interval(interval)

    # fetch candles
    candles = td_service.get_ohlc(symbol, interval_norm, outputsize=outputsize)
    df = pd.DataFrame(candles)
    if df.empty:
        raise ValueError("No OHLC data returned")

    # prepare dataframe
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)

    # Convert OHLC to numeric
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop volume if present
    if 'volume' in df.columns:
        df.drop(columns=['volume'], inplace=True)

    # prepare addplot (horizontal alert line) as Series aligned to df.index
    add_plots = []
    if alert_price is not None:
        alert_price = float(alert_price)
        alert_series = pd.Series([alert_price] * len(df), index=df.index)
        add_plots.append(
            mpf.make_addplot(
                alert_series,
                type='line',
                panel=0,
                color='#FFD400',   # bright yellow (change to 'red' if you prefer)
                linestyle='--',
                width=1.2,
                alpha=0.95
            )
        )

    # compute day-first timestamps for alines (first bar of each calendar day)
    try:
        day_firsts_series = df.index.to_series().groupby(df.index.date).first()
        if hasattr(day_firsts_series, "dt"):
            day_firsts = list(np.array(day_firsts_series.dt.to_pydatetime()))
        else:
            day_firsts = [pd.Timestamp(x).to_pydatetime() for x in day_firsts_series]
        idx_min = df.index[0]
        idx_max = df.index[-1]
        # keep only those within the index bounds and exclude the very first index if equal
        day_firsts = [d for d in day_firsts if d >= idx_min and d <= idx_max and d > idx_min]
    except Exception:
        day_firsts = []

    alines_dict = None
    if day_firsts:
        y_min = float(df['low'].min())
        y_max = float(df['high'].max())
        if alert_price is not None:
            y_min = min(y_min, alert_price)
            y_max = max(y_max, alert_price)
        vertical_lines = [
            ((pd.Timestamp(day).to_pydatetime(), y_min), (pd.Timestamp(day).to_pydatetime(), y_max))
            for day in day_firsts
        ]
        alines_dict = dict(
            alines=vertical_lines,
            colors=['#1f77b4'] * len(vertical_lines),  # blue
            linestyle=[':'] * len(vertical_lines),
            linewidths=[0.9] * len(vertical_lines),
            alpha=0.9
        )

    # create custom style based on 'yahoo' but with reduced font sizes
    small_font_rc = {
        'font.size': 6,
        'axes.labelsize': 6,
        'xtick.labelsize': 6,
        'ytick.labelsize': 6,
        'legend.fontsize': 6,
        'figure.titlesize': 7
    }
    custom_style = mpf.make_mpf_style(base_mpf_style='yahoo', rc=small_font_rc)

    # prepare mplfinance kwargs and write to BytesIO via savefig
    buf = BytesIO()
    plot_kwargs = dict(
        data=df,
        type='candle',
        style=custom_style,
        addplot=add_plots if add_plots else None,
        volume=False,
        figratio=(16, 9),
        figscale=1.0,
        savefig=dict(fname=buf, dpi=150, bbox_inches='tight'),
    )
    if alines_dict:
        plot_kwargs['alines'] = alines_dict

    # Avoid passing None to addplot
    if plot_kwargs.get('addplot') is None:
        plot_kwargs.pop('addplot')

    # Run mplfinance plot (writes into buf)
    mpf.plot(**plot_kwargs)

    # cleanup and return
    plt.close('all')
    buf.seek(0)
    return buf, interval_norm
