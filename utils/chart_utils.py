# utils/chart_utils.py
import matplotlib
matplotlib.use("Agg")

from io import BytesIO
import re
import numpy as np
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from utils.get_data import get_ohlc
from utils.normalize_data import normalize_timeframe, to_unix_timestamp
import time


def generate_chart_image(symbol: str, alert_price: float = None, timeframe: str = "15", from_date: int = None, to_date: int = time.time(), outputsize: int = 200):
    """
    Generate PNG chart for `symbol` at `interval` (interval can be '1h', '15m', '1440', etc).
    Returns: (BytesIO, period_minutes)
      - BytesIO is a PNG image buffer.
      - period_minutes is the integer minutes used with LiteFinance (e.g. 60 for '1h').
    """
    symbol = symbol.upper()

    timeframe_normalized = normalize_timeframe(timeframe)  # minute-based period for LiteFinance
    from_date_normalized = to_unix_timestamp(from_date)
    to_date_normalized = to_unix_timestamp(to_date)

    # --- fetch OHLC using new DataService ---
    try:
        raw = get_ohlc(
            symbol,
            timeframe_normalized,
            from_date_normalized,
            to_date_normalized,
            # outputsize=outputsize  # <-- now used to limit candles
        )
    except Exception as e:
        raise RuntimeError(f"Failed to fetch OHLC: {e}")

    # Accept either a DataFrame (preferred) or a list-of-dicts/list-of-lists fallback
    if isinstance(raw, pd.DataFrame):
        df = raw.copy()
    else:
        # try to coerce into DataFrame
        df = pd.DataFrame(raw)

    if df.empty:
        raise ValueError("No OHLC data returned")

    # Ensure datetime column / index exists
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        df.dropna(subset=["datetime"], inplace=True)
        df.set_index("datetime", inplace=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
        # try to coerce index to datetime
        try:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
            df.dropna(inplace=True)
        except Exception:
            raise ValueError("OHLC data missing 'datetime' column and index is not datetime")

    df.sort_index(inplace=True)

    # Ensure numeric OHLC columns
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # drop rows with NaNs in essential cols
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)

    if df.empty:
        raise ValueError("OHLC data contains no valid numeric rows")

    # Remove volume if present (we currently don't plot it)
    if "volume" in df.columns:
        df = df.drop(columns=["volume"])

    # Prepare addplot for alert price if provided
    add_plots = []
    if alert_price is not None:
        alert_price = float(alert_price)
        alert_series = pd.Series([alert_price] * len(df), index=df.index)
        add_plots.append(
            mpf.make_addplot(
                alert_series,
                type="line",
                panel=0,
                color="#FFD400",
                linestyle="--",
                width=1.2,
                alpha=0.95,
            )
        )

    # Determine whether to draw daily separators based on the user's rules:
    # - always show for timeframe 1 or 5
    # - for timeframe 15 or 60 (1h), show only when outputsize < 151
    # - never for other timeframes
    draw_daily_separators = False
    tf_digits = None
    try:
        m = re.search(r"(\d+)", str(timeframe))
        if m:
            tf_digits = m.group(1)
    except Exception:
        tf_digits = None

    if tf_digits in {"1", "5"}:
        draw_daily_separators = True
    elif tf_digits in {"15", "60"} and isinstance(outputsize, int) and outputsize < 151:
        draw_daily_separators = True
    else:
        draw_daily_separators = False

    # Compute day-first vertical lines only if allowed by the above logic
    day_firsts = []
    if draw_daily_separators:
        try:
            # group by calendar date, take first timestamp of each day
            day_firsts_series = df.index.to_series().groupby(df.index.date).first()
            idx_min, idx_max = df.index[0], df.index[-1]
            day_firsts = [d for d in day_firsts_series if idx_min < d <= idx_max]
        except Exception:
            day_firsts = []

    alines_dict = None
    if draw_daily_separators and day_firsts:
        y_min = float(df["low"].min())
        y_max = float(df["high"].max())
        if alert_price is not None:
            y_min = min(y_min, alert_price)
            y_max = max(y_max, alert_price)
        vertical_lines = [
            ((pd.Timestamp(day).to_pydatetime(), y_min), (pd.Timestamp(day).to_pydatetime(), y_max))
            for day in day_firsts
        ]
        alines_dict = dict(
            alines=vertical_lines,
            colors=["#1f77b4"] * len(vertical_lines),
            linestyle=[":"] * len(vertical_lines),
            linewidths=[0.9] * len(vertical_lines),
            alpha=0.9,
        )

    # small font style
    small_font_rc = {
        "font.size": 6,
        "axes.labelsize": 6,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "legend.fontsize": 6,
        "figure.titlesize": 7,
    }
    custom_style = mpf.make_mpf_style(base_mpf_style="yahoo", rc=small_font_rc)

    # plot to BytesIO
    buf = BytesIO()
    plot_kwargs = dict(
        data=df,
        type="candle",
        style=custom_style,
        addplot=add_plots if add_plots else None,
        volume=False,
        figratio=(16, 9),
        figscale=1.0,
        savefig=dict(fname=buf, dpi=150, bbox_inches="tight"),
        # silence mplfinance "too much data" warning by setting threshold a bit above our actual points
        warn_too_much_data=max(len(df) + 1, 1000),
    )
    if alines_dict:
        plot_kwargs["alines"] = alines_dict

    if plot_kwargs.get("addplot") is None:
        plot_kwargs.pop("addplot")

    mpf.plot(**plot_kwargs)
    plt.close("all")
    buf.seek(0)
    return buf, timeframe_normalized
