````markdown
# 📈 Great TR Bot

A **Telegram trading assistant bot** that helps you quickly fetch market data, charts, and manage price alerts — all from within Telegram.  
Supports multiple symbols, custom timeframes, and chart visualizations.

---

## ✨ Features

- **Price Lookup**  
  Get the latest Price / BID / ASK for any symbol.  
  ```bash
  /price eurusd
````

* **Charts on Demand**
  Request charts for one or multiple symbols, with flexible timeframes, output size, or date ranges.

  ```bash
  /chart EURUSD
  /chart EURUSD 60 300
  /chart EURUSD 60 "2024-08-01 14:30:00" "2025-01-01 14:30:00"
  /chart EURUSD,GBPUSD 15
  ```

* **Smart Alerts**
  Create price alerts with immediate chart snapshots for requested timeframes.

  ```bash
  /alert eurusd 1.1234 4h,15m
  ```

  ✅ Alerts trigger automatically when the condition is met.
  ✅ Inline buttons let you delete alerts directly.

* **Manage Alerts**
  List and manage all active alerts easily.

  ```bash
  /listalerts
  ```

* **Multiple Timeframe Support**
  Supports tokens like: `1m, 5m, 15m, 30m, 60/1h, 4h, D/1d, W, M`.

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/mubinxyz/great_tr_bot.git
cd great_tr_bot
```

### 2. Set up environment

Create a `.env` file with your bot and data provider credentials:

```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DATA_API_KEY=your_data_api_key   # e.g. for charts/prices
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the bot

```bash
python main.py
```

Now open your bot in Telegram and start with `/start`.

---

## 📌 Available Commands

### 💬 General

* `/start` — Start the bot
* `/help` — Show help message

### 💲 Price

* `/price <symbol>` — Get current price
  Example: `/price eurusd`

### 📊 Charts

* `/chart <symbols> [timeframe] [outputsize] [from_date] [to_date]`
  Example: `/chart EURUSD 60 "2024-08-01 14:30:00" "2025-01-01 14:30:00"`

### 🚨 Alerts

* `/alert <symbol> <price> <timeframes>`
  Example: `/alert eurusd 1.1234 4h,15m`

### 📭 Manage Alerts

* `/listalerts` — List & manage all alerts

---

## 🛠 Project Structure

```
great_tr_bot/
│── handlers/      # Telegram command handlers
│── models/        # Data models (alerts, user sessions, etc.)
│── services/      # External API & database services
│── strategies/    # Example trading strategies (e.g. MA crossover)
│── utils/         # Helper functions
│── bot.py        # Bot entry point
```

---

## 🗺 Roadmap

* [ ] Add email/SMS alert delivery
* [ ] More advanced chart overlays (indicators, trendlines)
* [ ] Backtesting integration for strategies
* [ ] Docker support for deployment

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss.

---

## 📜 License

MIT © 2025 [mubinxyz](https://github.com/mubinxyz)

