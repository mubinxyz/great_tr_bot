# backtest.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
import importlib.util
import os
import re
import traceback
import html as _html
from config import TD_STRATEGY_API_KEYS
from backtesting import Backtest
from services.strategy_twelvedata_service import StrategyTwelveDataService
import pandas as pd
from backtesting import Strategy as BacktestingStrategy  # for discovery

# Defaults (exposed in stats)
DEFAULT_CASH = 1000
DEFAULT_COMMISSION = 0.003
DEFAULT_ORDER_SIZE = 0.1


def normalize_symbol_for_td(sym: str) -> str:
    s = sym.strip().upper()
    if len(s) == 6 and s.isalpha():
        return s[:3] + "/" + s[3:]
    return s


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _main_menu_markup():
    keyboard = [
        [
            InlineKeyboardButton("📈 Trend-following", callback_data="bt_cat:trend_following"),
            InlineKeyboardButton("🔁 Mean-reversion", callback_data="bt_cat:mean_reversion"),
        ],
        [
            InlineKeyboardButton("⚙️ SMC", callback_data="bt_cat:smc"),
            InlineKeyboardButton("📦 Volume", callback_data="bt_cat:volume"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # works for both message and callback_query contexts; send/edit accordingly
    if update.callback_query:
        await update.callback_query.edit_message_text("Choose backtest category:", reply_markup=_main_menu_markup())
    else:
        await update.message.reply_text("Choose backtest category:", reply_markup=_main_menu_markup())


async def bt_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split(":", 1)[1]
    if cat == "trend_following":
        keyboard = [
            [
                InlineKeyboardButton("MA crossover — Basic", callback_data="bt_strat:ma_basic"),
                InlineKeyboardButton("MACD — Coming soon", callback_data="bt_strat:macd"),
            ],
            [
                InlineKeyboardButton("Bollinger — Coming soon", callback_data="bt_strat:bollinger"),
                InlineKeyboardButton("Back", callback_data="bt_back:main"),
            ],
        ]
        await query.edit_message_text("Trend-following strategies:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif cat == "mean_reversion":
        keyboard = [
            [InlineKeyboardButton("RSI Reversion — Coming soon", callback_data="bt_strat:rsi_rev")],
            [InlineKeyboardButton("Back", callback_data="bt_back:main")],
        ]
        await query.edit_message_text("Mean-reversion strategies (not implemented yet):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif cat == "smc":
        keyboard = [[InlineKeyboardButton("SMC — Coming soon", callback_data="bt_strat:smc_default")], [InlineKeyboardButton("Back", callback_data="bt_back:main")]]
        await query.edit_message_text("SMC strategies (not implemented yet):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif cat == "volume":
        keyboard = [[InlineKeyboardButton("Volume-based — Coming soon", callback_data="bt_strat:volume_default")], [InlineKeyboardButton("Back", callback_data="bt_back:main")]]
        await query.edit_message_text("Volume strategies (not implemented yet):", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("This category has no strategies implemented yet.")


async def bt_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    strat = query.data.split(":", 1)[1]
    if strat == "ma_basic":
        keyboard = [
            [InlineKeyboardButton("MA Basic — params (text)", callback_data="bt_ma:basic_params")],
            [InlineKeyboardButton("Back", callback_data="bt_back:main")],
        ]
        await query.edit_message_text(
            "MA Crossover — Basic.\nChoose how to input parameters:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        keyboard = [[InlineKeyboardButton("Back", callback_data="bt_back:main")]]
        await query.edit_message_text("This strategy is not implemented yet. Coming soon!", reply_markup=InlineKeyboardMarkup(keyboard))


async def bt_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = query.data.split(":", 1)[1]
    if target == "main":
        # edit back to main menu (do not call backtest_command which expects a message)
        await query.edit_message_text("Choose backtest category:", reply_markup=_main_menu_markup())
    else:
        await query.edit_message_text("Navigation target not recognized.")


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
            "I will run a quick backtest and return the stats and an HTML report (deleted after sending)."
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
        # allow user to optionally append order_size as 5th token (not required)
        order_size_override = None

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
            if len(parts) >= 5:
                order_size_override = float(parts[4])
        elif len(parts) >= 4:
            fast_ma = int(parts[1])
            slow_ma = int(parts[2])
            ma_type = parts[3].lower()
            if len(parts) >= 5:
                timeframe = parts[4].lower()
            if len(parts) >= 6:
                order_size_override = float(parts[5])
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
        raw = svc.get_ohlc(td_symbol, timeframe, outputsize=5000)
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

    # decide order_size (allow optional override in input)
    order_size = order_size_override if order_size_override is not None else DEFAULT_ORDER_SIZE

    strategy_kwargs = {
        "short_ma_length": fast_ma,
        "long_ma_length": slow_ma,
        "ma_type": ma_type,
        "order_size": order_size,
    }

    # Run backtest
    try:
        bt = Backtest(df, StrategyClass, cash=DEFAULT_CASH, commission=DEFAULT_COMMISSION)
        stats = bt.run(**strategy_kwargs)
    except Exception as e:
        tb = traceback.format_exc()
        await wait_msg.edit_text(f"❌ Backtest execution error:\n{e}\n\nTraceback:\n{tb[:1500]}")
        context.user_data.pop("bt_waiting", None)
        return

    # Build run params and include them in stats message
    run_params = {
        "symbol": symbol,
        "td_symbol": td_symbol,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "ma_type": ma_type,
        "timeframe": timeframe,
        "cash": DEFAULT_CASH,
        "commission": DEFAULT_COMMISSION,
        "order_size": order_size,
    }

    # Robust stats extraction & pretty-printing (include run_params)
    try:
        stats_dict = None
        if hasattr(stats, "_asdict"):
            try:
                stats_dict = stats._asdict()
            except Exception:
                stats_dict = None
        if stats_dict is None and isinstance(stats, dict):
            stats_dict = stats
        if stats_dict is None:
            try:
                import pandas as _pd
                if isinstance(stats, _pd.Series):
                    stats_dict = stats.to_dict()
                elif isinstance(stats, _pd.DataFrame):
                    if not stats.empty:
                        stats_dict = stats.iloc[0].to_dict()
            except Exception:
                pass
        if stats_dict is None and hasattr(stats, "to_dict"):
            try:
                stats_dict = stats.to_dict()
            except Exception:
                stats_dict = None
        if stats_dict is None:
            try:
                stats_dict = dict(stats)
            except Exception:
                stats_dict = None

        # merge run_params into top so user sees them clearly
        merged = {"run_params": run_params, "stats": stats_dict if stats_dict is not None else str(stats)}
        import pprint
        pretty = pprint.pformat(merged, width=120, indent=2)
        pretty_escaped = _html.escape(pretty)
        MAX_LEN = 3800
        if len(pretty_escaped) > MAX_LEN:
            pretty_escaped = pretty_escaped[:MAX_LEN] + "\n... (truncated)"
        await wait_msg.edit_text(f"<pre>{pretty_escaped}</pre>", parse_mode=ParseMode.HTML)
    except Exception:
        await wait_msg.edit_text("✅ Backtest finished — stats available (could not format nicely).")

    # Save HTML report, send it and delete immediately
    out_path = None
    try:
        sym_for_name = symbol.replace("/", "-").replace("\\", "-")
        raw_name = f"backtest_{sym_for_name}_{fast_ma}_{slow_ma}_{ma_type}_{timeframe}.html"
        safe_name = _sanitize_filename(raw_name)
        out_path = os.path.join(os.getcwd(), safe_name)

        bt.plot(filename=out_path, open_browser=False)

        try:
            with open(out_path, "rb") as fh:
                await update.message.reply_document(document=fh, filename=os.path.basename(out_path))
        except Exception as e_file:
            tb = traceback.format_exc()
            await update.message.reply_text(f"⚠️ Could not send HTML report: {e_file}\n\nTraceback:\n{tb[:1500]}")
        finally:
            if out_path and os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except Exception:
                    pass

    except Exception as e:
        tb = traceback.format_exc()
        await update.message.reply_text(f"⚠️ Could not generate/send HTML report: {e}\n\nTraceback:\n{tb[:1500]}")
    finally:
        context.user_data.pop("bt_waiting", None)


def register_backtest_handlers(app):
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CallbackQueryHandler(bt_category_callback, pattern=r"^bt_cat:.+"))
    app.add_handler(CallbackQueryHandler(bt_strategy_callback, pattern=r"^bt_strat:.+"))
    app.add_handler(CallbackQueryHandler(bt_back_callback, pattern=r"^bt_back:.+"))
    app.add_handler(CallbackQueryHandler(bt_ma_variant_callback, pattern=r"^bt_ma:.+"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bt_ma_params_received))
