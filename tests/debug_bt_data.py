# debug_bt_data.py
from services.backtest_data_service import fetch_backtest_data

df = fetch_backtest_data("eurusd", "1h", output_size=10)
print(df.head())
print(df.tail())
