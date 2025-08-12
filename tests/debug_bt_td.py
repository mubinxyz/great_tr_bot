# debug_bt_td.py
from services.strategy_twelvedata_service import BacktestTwelveDataService

svc = BacktestTwelveDataService()
print("Using key:", svc.current_api_key)
print("Price EURUSD:", svc.get_price("eurusd"))
print("Sample candles (count):", len(svc.get_ohlc("eurusd", "1h", outputsize=5)))
