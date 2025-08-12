# ma_basic_c.py
import pandas as pd
import numpy as np
try:
    import pandas_ta as pta
except Exception:
    pta = None

from backtesting import Strategy
from backtesting.lib import crossover


def to_series(x) -> pd.Series:
    """
    Convert array-like/backtesting._Array/pd.Series to a pandas Series,
    trying to preserve an index if present.
    """
    # If already a Series, just ensure float dtype
    if isinstance(x, pd.Series):
        return x.astype(float)

    # Try to get numpy array view
    try:
        vals = np.asarray(x)
    except Exception:
        # fallback: try to iterate
        vals = np.array(list(x))

    # Try to preserve index from the original object if available and length matches
    idx = getattr(x, "index", None)
    if idx is not None and len(idx) == len(vals):
        return pd.Series(vals, index=idx).astype(float)

    # Otherwise create a default RangeIndex
    return pd.Series(vals, index=pd.RangeIndex(len(vals))).astype(float)


def ssma(close_data: pd.Series, ssma_length: int) -> pd.Series:
    """
    Smoothed Simple Moving Average (SSMA).
    Works with backtesting._Array and other array-likes.
    """
    series = to_series(close_data)
    if ssma_length <= 0:
        raise ValueError("ssma_length must be > 0")

    # If not enough data, return simple rolling mean aligned to original index
    if len(series) < ssma_length:
        return series.rolling(ssma_length).mean()

    # compute ssma on the integer positional index, then restore original index
    values = series.to_numpy(copy=True).astype(float)
    ssma_vals = np.empty_like(values)
    # initial window: simple mean
    initial_mean = values[:ssma_length].mean()
    ssma_vals[:ssma_length] = initial_mean
    for i in range(ssma_length, len(values)):
        ssma_vals[i] = (ssma_vals[i - 1] * (ssma_length - 1) + values[i]) / ssma_length

    return pd.Series(ssma_vals, index=series.index)


def ema(close_data: pd.Series, ema_length: int) -> pd.Series:
    """
    Exponential Moving Average; prefer pandas_ta if available, otherwise pandas ewm.
    Works with backtesting._Array and other array-likes.
    """
    series = to_series(close_data)
    if ema_length <= 0:
        raise ValueError("ema_length must be > 0")

    # Try pandas_ta first (user has pandas_ta)
    if pta is not None:
        try:
            # pandas_ta has multiple function signatures across versions; try sensible calls
            try:
                res = pta.ema(series, length=ema_length)
            except TypeError:
                # different signature in some versions
                res = pta.ema(close=series, length=ema_length)
            # If DataFrame returned, pick first column
            if isinstance(res, pd.DataFrame):
                res = res.iloc[:, 0]
            # ensure correct index & dtype
            res.index = series.index
            return res.astype(float)
        except Exception:
            # fall back to pandas ewm on any error
            pass

    # Fallback to pandas ewm
    return series.ewm(span=ema_length, adjust=False).mean()


class Ma_cross(Strategy):
    """
    Moving Average Crossover strategy.
    Parameters (overridden via Backtest strategy_kwargs):
      - short_ma_length: int
      - long_ma_length: int
      - ma_type: 'ssma', 'ema', or 'ma' (simple MA)
    """

    short_ma_length = 50
    long_ma_length = 200
    ma_type = "ssma"  # 'ssma', 'ema', or 'ma'

    def init(self):
        mtype = getattr(self, "ma_type", "ssma").lower()
        if mtype == "ssma":
            ma_func = ssma
        elif mtype == "ema":
            ma_func = ema
        else:
            # simple moving average - use pandas rolling mean via a wrapper
            ma_func = lambda series, length: to_series(series).rolling(length).mean()

        # Read lengths - allow both possible kwarg names if present
        short_len = int(getattr(self, "short_ma_length", getattr(self, "fast_ma_length", self.short_ma_length)))
        long_len = int(getattr(self, "long_ma_length", getattr(self, "slow_ma_length", self.long_ma_length)))

        self.short_ma_length = short_len
        self.long_ma_length = long_len
        self.ma_type = mtype

        # Use self.I to register indicators — pass the raw self.data.Close (backtesting._Array),
        # the wrapper will convert inside the functions.
        self.short_ma = self.I(ma_func, self.data.Close, self.short_ma_length)
        self.long_ma = self.I(ma_func, self.data.Close, self.long_ma_length)

    def next(self):
        if crossover(self.short_ma, self.long_ma):
            if self.position.is_short:
                self.position.close()
            self.buy(size=0.1)
        elif crossover(self.long_ma, self.short_ma):
            if self.position.is_long:
                self.position.close()
            self.sell(size=0.1)
