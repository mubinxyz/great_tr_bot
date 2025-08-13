from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from urllib.parse import urlparse, parse_qs
import json, time

def fetch_last_price_json(symbol="EURUSD", headless=True, timeout=30000):
    """
    Returns a JSON string: {"asset": "EURUSD", "bid": float, "ask": float, "price": float}
    Accepts either a symbol like "EURUSD" or a full URL (e.g. https://.../trading/chart?symbol=EURUSD).
    """
    parsed = urlparse(symbol)
    if parsed.scheme and parsed.netloc:
        url = symbol
        qs = parse_qs(parsed.query)
        asset = (qs.get("symbol", [None])[0] or "").upper()
    else:
        asset = symbol.strip().upper()
        url = f"https://my.litefinance.org/trading/chart?symbol={asset}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except PWTimeout:
                pass

            # small pause for client-side rendering
            time.sleep(0.6)

            bid_el = page.wait_for_selector("span.field_type_value.js_value_price_bid", timeout=10000)
            ask_el = page.wait_for_selector("span.field_type_value.js_value_price_ask", timeout=10000)

            bid = float(bid_el.inner_text().strip())
            ask = float(ask_el.inner_text().strip())
            price = (bid + ask) / 2.0

            result = {"asset": asset or "", "bid": bid, "ask": ask, "price": price}
            return json.dumps(result)
        finally:
            try:
                browser.close()
            except:
                pass

# if __name__ == "__main__":
#     print(fetch_last_price_json("https://my.litefinance.org/trading/chart?symbol=EURUSD", headless=True))
