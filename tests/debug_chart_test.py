# debug_chart_test.py
from services.chart_service import generate_chart_image
buf, interval = generate_chart_image("eurusd", "1h", alert_price=1.12345)
with open("debug_chart.png", "wb") as f:
    f.write(buf.getbuffer())
print("Saved debug_chart.png interval:", interval)