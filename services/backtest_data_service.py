# services/backtest_data_service.py
import pandas as pd
from services.backtest_twelvedata_service import BacktestTwelveDataService

bt_service = BacktestTwelveDataService()

def fetch_backtest_data(symbol: str, interval: str, output_size: int = 500) -> pd.DataFrame:
    """
    Fetch OHLC data for backtesting.
    Returns a DataFrame indexed by datetime with columns:
    ['Open', 'High', 'Low', 'Close', 'Volume'] (volume may be NaN if not provided).
    """
    raw_data = bt_service.get_ohlc(symbol, interval, outputsize=output_size)

    # convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    # normalize column names
    df.columns = [col.capitalize() for col in df.columns]
    
    # ensure datetime index
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)

    # numeric conversions
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Volume' in df.columns:
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
    else:
        df['Volume'] = None

    # sort ascending
    df.sort_index(inplace=True)

    return df
