import requests
from bs4 import BeautifulSoup
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_last_data(symbol: str = "EURUSD"):
    symbol = symbol.upper()
    url = f"https://my.litefinance.org/trading/chart?symbol={symbol}"
    
    # Create a session with retry mechanism
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = session.get(url, headers=headers, timeout=10, verify=False)  # SSL verification disabled for testing
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        bid = float(soup.find("span", attrs={"class": ["field_type_value", "js_value_price_bid"]}).get_text())
        ask = float(soup.find("span", attrs={"class": ["field_type_value", "js_value_price_ask"]}).get_text())
        price = (bid + ask) / 2.0

        data = {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "price": price
        }
        return json.dumps(data)
    
    except requests.exceptions.SSLError as ssl_err:
        print(f"SSL Error: {ssl_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Request Error: {req_err}")
        return None
    except AttributeError as attr_err:
        print(f"Parsing Error: {attr_err}")
        return None
    finally:
        session.close()

# Main loop
end_time = time.time() + 15

while time.time() < end_time:
    result = get_last_data()
    if result:
        print(result)
    # time.sleep()  # Increased sleep to avoid rate-limiting