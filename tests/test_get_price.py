# test_get_price.py
from utils.get_data import get_price, get_ohlc
from utils.scrape_last_data import get_last_data
from utils.normalize_data import normalize_symbol

sym = "EURUSD"

# 1) direct get_price call (what your bot runs)
print("get_price:", get_price(sym))

# 2) test the scraper helper result (most fragile)
res = get_last_data(sym)
print("get_last_data raw:", type(res), res)
try:
    print("get_last_data.json():", res.json())
except Exception as e:
    print("get_last_data.json() raised:", e)

# 3) test normalization used for TwelveData
print("normalize_symbol:", normalize_symbol(sym))

# 4) test ohlc quickly (TwelveData fallback path)
print("get_ohlc (first 3 rows):")
df = get_ohlc(sym, timeframe=15)
print(df.head(3))
