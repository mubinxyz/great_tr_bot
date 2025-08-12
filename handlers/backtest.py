from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import importlib.util
import os
from config import TD_STRATEGY_API_KEYS
from services.strategy_data_service import fetch_ohlcv_data
from backtesting import Backtest

# --- Step 1: /backtest ---
async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📈 Trend-following", callback_data="bt_cat:trend_following")],
        [InlineKeyboardButton("💹 Mean-reversion (soon)", callback_data="bt_cat:mean_reversion")],
        [InlineKeyboardButton("📊 SMC (soon)", callback_data="bt_cat:smc")],
        [InlineKeyboardButton("📦 Volume (soon)", callback_data="bt_cat:volume")]
    ]
    await update.message.reply_text(
        "Choose backtest category:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Step 2: Category chosen ---
async def bt_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":")[1]

    if category == "trend_following":
        keyboard = [
            [InlineKeyboardButton("MA Crossover", callback_data="bt_strat:ma_crossover")],
            [InlineKeyboardButton("2MA+MACD", callback_data="bt_strat:2_ma_macd")],
            [InlineKeyboardButton("3MA_2_OF_THEM_CROSS", callback_data="bt_strat:3_ma_2_of_them_cross")],
        ]
        await query.edit_message_text("Choose trend-following strategy:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("🚧 This category is coming soon!")

# --- Step 3: Strategy chosen ---
async def bt_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    strategy = query.data.split(":")[1]

    if strategy == "ma_crossover":
        keyboard = [
            [InlineKeyboardButton("Basic", callback_data="bt_ma:ma_basic_c")],
            [InlineKeyboardButton("Session-based", callback_data="bt_ma:ma_session_c")],
            [InlineKeyboardButton("ATR-based SL/TP", callback_data="bt_ma:ma_atr_c")],
            [InlineKeyboardButton("% Stop Loss", callback_data="bt_ma:ma_percent_c")]
        ]
        await query.edit_message_text("Choose MA crossover variant:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("🚧 This strategy is coming soon!")

# --- Step 4: Variant chosen ---
async def bt_ma_variant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    variant = query.data.split(":")[1]
    context.user_data["bt_variant"] = variant

    if variant == "ma_basic_c":
        text = (
            f"Selected: {variant.replace('_', ' ').title()}\n\n"
            "Now reply with:\n"
            "`SYMBOL FAST_MA,SLOW_MA MA_TYPE TIMEFRAME`\n"
            "Example: `EURUSD 10,20 ema 1h`"
        )
    else:
        text = (
            f"Selected: {variant.replace('_', ' ').title()}\n\n"
            "coming soon"
        )

    await query.edit_message_text(text, parse_mode="Markdown")

# --- Step 5: Run backtest ---
async def bt_ma_params_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    variant = context.user_data.get("bt_variant")

    if not variant:
        await update.message.reply_text("⚠️ Please select a strategy variant first.")
        return

    if variant == "ma_basic_c":
        # Expecting: SYMBOL FAST_MA,SLOW_MA MA_TYPE TIMEFRAME
        # Example: EURUSD 10,20 ema 1h
        parts = user_text.split()
        if len(parts) != 4:
            await update.message.reply_text(
                "⚠️ Wrong format! Please reply exactly like:\n"
                "`SYMBOL FAST_MA,SLOW_MA MA_TYPE TIMEFRAME`\n"
                "Example: `EURUSD 10,20 ema 1h`",
                parse_mode="Markdown"
            )
            return

        symbol = parts[0].upper()
        ma_pair = parts[1].split(",")
        if len(ma_pair) != 2 or not all(x.isdigit() for x in ma_pair):
            await update.message.reply_text("⚠️ FAST_MA and SLOW_MA must be two integers separated by a comma, e.g. 10,20")
            return
        fast_ma, slow_ma = map(int, ma_pair)
        ma_type = parts[2].lower()
        timeframe = parts[3].lower()

        valid_ma_types = ["ma", "ema", "ssma"]  # add more if you want
        if ma_type not in valid_ma_types:
            await update.message.reply_text(
                f"⚠️ Invalid MA_TYPE. Choose one of: {', '.join(valid_ma_types)}"
            )
            return

        # Store parsed params for next step
        context.user_data["bt_params"] = {
            "symbol": symbol,
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "ma_type": ma_type,
            "timeframe": timeframe,
        }

        await update.message.reply_text(
            f"✅ Parameters received:\n"
            f"Symbol: {symbol}\n"
            f"Fast MA: {fast_ma}\n"
            f"Slow MA: {slow_ma}\n"
            f"MA Type: {ma_type}\n"
            f"Timeframe: {timeframe}\n\n"
            "Now running backtest..."
        )

        # Here you can call the backtest function with those params or schedule it
        # For example:
        # stats, plot_path = await run_ma_basic_c_backtest(context.user_data["bt_params"])
        # await update.message.reply_photo(photo=open(plot_path, 'rb'), caption=f"Backtest stats:\n{stats}")

    else:
        await update.message.reply_text("⚠️ This variant is not yet implemented.")

# --- Register ---
def register_backtest_handlers(app):
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CallbackQueryHandler(bt_category_callback, pattern=r"^bt_cat:.+"))
    app.add_handler(CallbackQueryHandler(bt_strategy_callback, pattern=r"^bt_strat:.+"))
    app.add_handler(CallbackQueryHandler(bt_ma_variant_callback, pattern=r"^bt_ma:.+"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bt_params_handler))
