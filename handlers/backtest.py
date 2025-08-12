# backtest.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import importlib.util
import os
import traceback
from config import TD_STRATEGY_API_KEYS
from backtesting import Backtest
from services.strategy_twelvedata_service import StrategyTwelveDataService
import pandas as pd
from backtesting import Strategy as BacktestingStrategy  # for discovery


def normalize_symbol_for_td(sym: str) -> str:
    s = sym.strip().upper()
    if len(s) == 6 and s.isalpha():
        return s[:3] + "/" + s[3:]
    return s


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📈 Trend-following", callback_data="bt_cat:trend_following")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose backtest category:", reply_markup=reply_markup)


async def bt_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split(":", 1)[1]
    if cat == "trend_following":
        keyboard = [
            [InlineKeyboardButton("MA crossover — Basic", callback_data="bt_strat:ma_basic")],
        ]
        await query.edit_message_text("Trend-following strategies:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("This category has no strategies implemented yet.")


async def bt_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    strat = query.data.split(":", 1)[1]
    if strat == "ma_basic":
        keyboard = [
            [InlineKeyboardButton("MA Basic — params (text)", callback_data="bt_ma:basic_params")],
        ]
        await query.edit_message_text(
            "MA Crossover — Basic.\nChoose how to input parameters:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text("Strategy not implemented.")


async def bt_ma_variant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    variant = query.data.split(":", 1)[1]
    if variant == "basic_params":
        context.user_data["bt_waiting"] = "ma_basic"
        msg = (
            "Send parameters as text in one of these forms:\n\n"
            "1) SYMBOL FAST,SLOW MA_TYPE TIMEFRAME\n"
            "   e.g. `EURUSD 10,50 ssma 1h`\n\n"
            "2) SYMBOL FAST SLOW MA_TYPE TIMEFRAME\n"
            "   e.g. `EUR/USD 10 50 ema 4h`\n\n"
            "Accepted MA_TYPE: ssma | sma | ema\n"
            "Accepted TIMEFRAME examples: 1min 5min 15min 1h 4h 1day\n\n"
            "I will run a quick backtest and return the stats."
        )
        await query.edit_message_text(msg)
    else:
        await query.edit_message_text("Variant not implemented.")


async def bt_ma_params_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("bt_waiting") != "ma_basic":
        return

    text = update.message.text or ""
    wait_msg = await update.message.reply_text("⏳ Running backtest — parsing parameters...")

    parts = text.strip().split()
    try:
        symbol = None
        fast_ma = None
        slow_ma = None
        ma_type = "ssma"
        timeframe = "1h"

        if len(parts) >= 1:
            symbol = parts[0]
        if len(parts) >= 2 and "," in parts[1]:
            nums = parts[1].split(",")
            fast_ma = int(nums[0])
            slow_ma = int(nums[1])
            if len(parts) >= 3:
                ma_type = parts[2].lower()
            if len(parts) >= 4:
                timeframe = parts[3].lower()
        elif len(parts) >= 4:
            fast_ma = int(parts[1])
            slow_ma = int(parts[2])
            ma_type = parts[3].lower()
            if len(parts) >= 5:
                timeframe = parts[4].lower()
        else:
            if len(parts) == 3:
                symbol = parts[0]
                fast_ma = int(parts[1])
                slow_ma = int(parts[2])
                ma_type = "ssma"
            else:
                raise ValueError("Could not parse parameters from input.")

        if ma_type not in ("sma", "ema", "ssma"):
            raise ValueError("ma_type must be 'sma', 'ema', or 'ssma'.")

        td_symbol = normalize_symbol_for_td(symbol)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Parameter parse error: {e}\n\nPlease follow the format described earlier.")
        context.user_data.pop("bt_waiting", None)
        return

    try:
        svc = StrategyTwelveDataService()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Strategy service not configured: {e}")
        context.user_data.pop("bt_waiting", None)
        return

    try:
        raw = svc.get_ohlc(td_symbol, timeframe, outputsize=500)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Failed to fetch OHLC for {td_symbol}: {e}")
        context.user_data.pop("bt_waiting", None)
        return

    try:
        df = pd.DataFrame(raw)
        df.rename(
            columns={
                "datetime": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            },
            inplace=True,
        )
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)
        if len(df) < max(fast_ma, slow_ma) + 5:
            await wait_msg.edit_text(
                f"❌ Not enough data points for short={fast_ma}, long={slow_ma}. Only {len(df)} rows fetched."
            )
            context.user_data.pop("bt_waiting", None)
            return
    except Exception as e:
        await wait_msg.edit_text(f"❌ Error preparing OHLC DataFrame: {e}")
        context.user_data.pop("bt_waiting", None)
        return

    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(base_dir, "strategies", "trend_following", "ma_crossover", "ma_basic_c.py"),
        os.path.join(base_dir, "ma_basic_c.py"),
        os.path.join(os.getcwd(), "strategies", "trend_following", "ma_crossover", "ma_basic_c.py"),
        os.path.join(os.getcwd(), "ma_basic_c.py"),
    ]

    module = None
    last_import_error = None
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ma_basic_c", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            break
        except Exception as e:
            last_import_error = e
            module = None

    if module is None:
        msg = f"❌ Could not import strategy module. Tried paths:\n" + "\n".join(candidates)
        if last_import_error:
            msg += f"\n\nLast import error: {last_import_error}"
        await wait_msg.edit_text(msg)
        context.user_data.pop("bt_waiting", None)
        return

    StrategyClass = None
    for obj in module.__dict__.values():
        if isinstance(obj, type) and issubclass(obj, BacktestingStrategy) and obj is not BacktestingStrategy:
            StrategyClass = obj
            break

    if StrategyClass is None:
        await wait_msg.edit_text("❌ No Strategy subclass found in the imported strategy module.")
        context.user_data.pop("bt_waiting", None)
        return

    strategy_kwargs = {
        "short_ma_length": fast_ma,
        "long_ma_length": slow_ma,
        "ma_type": ma_type,
    }

    # --- IMPORTANT CHANGE: don't pass strategy_kwargs to Backtest.__init__ ---
    try:
        bt = Backtest(df, StrategyClass, cash=1000, commission=0.003)
        # pass strategy kwargs to .run(...) — the Backtest.run() forwards them to the Strategy
        stats = bt.run(**strategy_kwargs)
    except Exception as e:
        tb = traceback.format_exc()
        await wait_msg.edit_text(f"❌ Backtest execution error:\n{e}\n\nTraceback:\n{tb[:1500]}")
        context.user_data.pop("bt_waiting", None)
        return

    try:
        stats_text = "✅ Backtest finished — summary:\n\n"
        stats_df = getattr(stats, "_asdict", None)
        if callable(stats_df):
            stats_text += str(stats._asdict())
        else:
            stats_text += str(stats)
        await wait_msg.edit_text(stats_text)
    except Exception:
        await wait_msg.edit_text("✅ Backtest finished — stats available. (Could not format nicely.)")

    context.user_data.pop("bt_waiting", None)


def register_backtest_handlers(app):
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CallbackQueryHandler(bt_category_callback, pattern=r"^bt_cat:.+"))
    app.add_handler(CallbackQueryHandler(bt_strategy_callback, pattern=r"^bt_strat:.+"))
    app.add_handler(CallbackQueryHandler(bt_ma_variant_callback, pattern=r"^bt_ma:.+"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bt_ma_params_received))
