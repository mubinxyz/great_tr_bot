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
    if isinstance(x, pd.Series):
        return x.astype(float)
    try:
        vals = np.asarray(x)
    except Exception:
        vals = np.array(list(x))
    idx = getattr(x, "index", None)
    if idx is not None and len(idx) == len(vals):
        return pd.Series(vals, index=idx).astype(float)
    return pd.Series(vals, index=pd.RangeIndex(len(vals))).astype(float)


def ssma(close_data: pd.Series, ssma_length: int) -> pd.Series:
    series = to_series(close_data)
    if ssma_length <= 0:
        raise ValueError("ssma_length must be > 0")
    if len(series) < ssma_length:
        return series.rolling(ssma_length).mean()
    values = series.to_numpy(copy=True).astype(float)
    ssma_vals = np.empty_like(values)
    initial_mean = values[:ssma_length].mean()
    ssma_vals[:ssma_length] = initial_mean
    for i in range(ssma_length, len(values)):
        ssma_vals[i] = (ssma_vals[i - 1] * (ssma_length - 1) + values[i]) / ssma_length
    return pd.Series(ssma_vals, index=series.index)


def ema(close_data: pd.Series, ema_length: int) -> pd.Series:
    series = to_series(close_data)
    if ema_length <= 0:
        raise ValueError("ema_length must be > 0")
    if pta is not None:
        try:
            try:
                res = pta.ema(series, length=ema_length)
            except TypeError:
                res = pta.ema(close=series, length=ema_length)
            if isinstance(res, pd.DataFrame):
                res = res.iloc[:, 0]
            res.index = series.index
            return res.astype(float)
        except Exception:
            pass
    return series.ewm(span=ema_length, adjust=False).mean()


class Ma_cross(Strategy):
    """
    MA crossover strategy.
    Accepts strategy kwargs:
      - short_ma_length (int)
      - long_ma_length (int)
      - ma_type ('ssma'|'ema'|'ma')
      - order_size (float)  <-- new: size passed to buy/sell
    """

    short_ma_length = 50
    long_ma_length = 200
    ma_type = "ssma"
    # NOTE: default order_size is kept here in case no strategy_kwarg provided
    order_size = 0.1

    def init(self):
        mtype = getattr(self, "ma_type", "ssma").lower()
        if mtype == "ssma":
            ma_func = ssma
        elif mtype == "ema":
            ma_func = ema
        else:
            ma_func = lambda series, length: to_series(series).rolling(length).mean()

        short_len = int(getattr(self, "short_ma_length", getattr(self, "fast_ma_length", self.short_ma_length)))
        long_len = int(getattr(self, "long_ma_length", getattr(self, "slow_ma_length", self.long_ma_length)))

        # order_size may be provided via strategy kwargs; default to class attribute
        self.order_size = float(getattr(self, "order_size", Ma_cross.order_size))

        self.short_ma_length = short_len
        self.long_ma_length = long_len
        self.ma_type = mtype

        self.short_ma = self.I(ma_func, self.data.Close, self.short_ma_length)
        self.long_ma = self.I(ma_func, self.data.Close, self.long_ma_length)

    def next(self):
        # use self.order_size when opening orders
        if crossover(self.short_ma, self.long_ma):
            if self.position.is_short:
                self.position.close()
            self.buy(size=self.order_size)
        elif crossover(self.long_ma, self.short_ma):
            if self.position.is_long:
                self.position.close()
            self.sell(size=self.order_size)
