# handlers/alert.py
import asyncio
import functools
import logging
from telegram.ext import CommandHandler
from telegram import Update
from services.user_service import get_or_create_user
from services.alert_service import create_alert
from services.chart_service import get_chart
from utils.normalize_data import normalize_timeframe, normalize_symbol
from utils.get_data import get_price  # added import to fetch current price for trigger message

logger = logging.getLogger(__name__)
INTER_CHART_DELAY = 0.1  # polite pause between charts

# default timeframe when user omits it
DEFAULT_TF = "60"

# sensible fallback timeframes (canonical tokens your normalize_timeframe likely returns).
# Order matters: try requested tf first, then these if it fails.
FALLBACK_TFS = ["1", "5", "15", "60"]


async def _try_get_chart_with_fallback(loop, symbol, tf_token, alert_price, outputsize=150):
    """
    Try to get a chart for tf_token via services.chart_service.get_chart.
    If get_chart raises an error indicating no OHLC data, try fallback timeframes.
    Returns (buf, interval_norm, used_tf) on success, or raises the last exception.
    """
    last_exc = None

    # build candidate list: requested token first, then fallbacks (avoid duplicates)
    candidates = [tf_token] + [t for t in FALLBACK_TFS if t != tf_token]

    for cand in candidates:
        # ensure we pass a normalized token to get_chart (defensive)
        try:
            tf_for_chart = normalize_timeframe(cand)
        except Exception:
            tf_for_chart = cand

        try:
            call_plot = functools.partial(
                get_chart,
                symbol=symbol,
                timeframe=tf_for_chart,
                alert_price=alert_price,
                outputsize=outputsize,
                from_date=None,
                to_date=None
            )
            buf, interval_norm = await loop.run_in_executor(None, call_plot)
            return buf, interval_norm, tf_for_chart
        except Exception as e:
            last_exc = e
            # if the error message indicates missing OHLC data, try next fallback
            msg = str(e).lower()
            if "no ohlc" in msg or "no ohlc data" in msg or "no data" in msg:
                logger.info("No OHLC for %s %s — trying next fallback", symbol, cand)
                continue
            # otherwise, for other errors, break and re-raise
            logger.exception("Chart generation failed for %s %s: %s", symbol, cand, e)
            break

    # exhausted candidates — raise last exception
    if last_exc:
        raise last_exc
    raise RuntimeError("Chart generation failed (unknown reason)")


async def alert_command(update: Update, context):
    """
    /alert SYMBOL PRICE [TIMEFRAMES]
    Example:
      /alert eurusd 1.1234 4h,15m
      /alert eurusd 1.1234        -> uses default timeframe (DEFAULT_TF)

    This command:
      - creates an alert in DB (decides direction vs current market price)
      - returns charts immediately for given timeframes with an alert line
      - if the alert is already triggered at creation time, send the trigger message (with price/bid/ask)
    """
    # require at least symbol + price
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /alert SYMBOL PRICE [TIMEFRAMES]\nExample: /alert eurusd 1.2345 4h,15m (timeframes optional)"
        )
        return

    symbol = context.args[0].strip()
    price_raw = context.args[1].strip()

    # safe extraction of optional timeframes argument
    if len(context.args) >= 3 and context.args[2].strip():
        tfs_raw = context.args[2].strip()
    else:
        tfs_raw = DEFAULT_TF

    # parse price
    try:
        price = float(price_raw)
    except Exception:
        await update.message.reply_text("⚠️ Invalid price format. Use something like: 1.2345")
        return

    # parse/normalize timeframes (comma-separated)
    tfs_list = [s.strip() for s in tfs_raw.split(",") if s.strip()]
    if not tfs_list:
        # fallback to default
        tfs_list = [DEFAULT_TF]

    normalized_tfs = []
    for tf in tfs_list:
        try:
            normalized_tfs.append(normalize_timeframe(tf))
        except Exception as e:
            await update.message.reply_text(f"⚠️ Invalid timeframe '{tf}': {e}")
            return

    loop = asyncio.get_running_loop()

    # 1) Ensure user exists (DB likely blocking) -> run in executor
    try:
        call_user = functools.partial(
            get_or_create_user,
            chat_id=update.effective_chat.id,
            username=(update.effective_user.username if update.effective_user else None),
            first_name=(update.effective_user.first_name if update.effective_user else None),
            last_name=(update.effective_user.last_name if update.effective_user else None),
        )
        user = await loop.run_in_executor(None, call_user)
    except Exception as e:
        logger.exception("Failed to get/create user")
        await update.message.reply_text(f"⚠️ Failed to access user record: {e}")
        return

    # 2) Create alert (blocking DB call) in executor
    try:
        norm_symbol = normalize_symbol(symbol)

        call_alert = functools.partial(
            create_alert,
            user_id=user.id,
            symbol=norm_symbol,
            target_price=price,
            timeframes=normalized_tfs,
        )
        alert = await loop.run_in_executor(None, call_alert)
    except Exception as e:
        logger.exception("Failed to create alert")
        await update.message.reply_text(f"⚠️ Failed to create alert: {e}")
        return

    # Determine canonical timeframe display (prefer stored alert.timeframes if available)
    try:
        tf_display = alert.timeframes if getattr(alert, "timeframes", None) else ",".join(normalized_tfs)
    except Exception:
        tf_display = ",".join(normalized_tfs)

    # If service returned an existing duplicate alert, inform the user and show its details
    is_duplicate = bool(getattr(alert, "_is_duplicate", False))
    try:
        if is_duplicate:
            try:
                await update.message.reply_text(
                    f"⚠️ You already have an equivalent pending alert (ID: {getattr(alert, 'id', '?')}). "
                    f"Existing alert: {getattr(alert, 'symbol', norm_symbol)} "
                    f"{getattr(alert.direction, 'value', str(alert.direction)).lower()} "
                    f"{getattr(alert, 'target_price', '?')} on {tf_display}\nShowing charts for the existing alert."
                )
            except Exception:
                logger.debug("Failed to send duplicate info to user", exc_info=True)
        else:
            # new alert — send the saved confirmation
            try:
                direction = getattr(alert.direction, "value", str(alert.direction))
                await update.message.reply_text(
                    f"✅ Alert saved: {alert.symbol} {direction} {alert.target_price} on {tf_display}\nAlert ID: {alert.id}"
                )
            except Exception:
                await update.message.reply_text(f"✅ Alert saved (ID unknown).")
    except Exception:
        logger.exception("Failed while sending alert confirmation/duplicate notice for alert %s", getattr(alert, "id", "?"))

    # If alert already triggered on creation, notify user with a trigger-style message (including price/bid/ask)
    try:
        if getattr(alert, "triggered", False):
            # attempt to fetch current price info so we can include current price/bid/ask details
            try:
                call_price = functools.partial(get_price, getattr(alert, "symbol", norm_symbol))
                price_resp = await loop.run_in_executor(None, call_price)
            except Exception as e:
                logger.warning("Failed to fetch price for trigger message: %s", e)
                price_resp = None

            # extract numeric and fields
            current_price = None
            bid_val = None
            ask_val = None
            last_val = None

            if isinstance(price_resp, dict):
                last_val = price_resp.get("price") or price_resp.get("last") or price_resp.get("close") or price_resp.get("last_price")
                bid_val = price_resp.get("bid")
                ask_val = price_resp.get("ask")
                # try to coerce current numeric price
                for key in ("price", "last", "close", "last_price"):
                    v = price_resp.get(key)
                    if v is not None:
                        try:
                            current_price = float(v)
                            break
                        except Exception:
                            continue
                # fallback: scan values for numeric-like
                if current_price is None:
                    for v in price_resp.values():
                        try:
                            current_price = float(v)
                            break
                        except Exception:
                            continue
            else:
                # numeric-like
                try:
                    if price_resp is not None:
                        current_price = float(price_resp)
                        last_val = current_price
                except Exception:
                    current_price = None

            def _fmt(val):
                if val is None:
                    return "N/A"
                try:
                    return f"{float(val):.6f}"
                except Exception:
                    return str(val)

            direction_val = getattr(alert.direction, "value", str(alert.direction)).upper() if getattr(alert, "direction", None) is not None else ""
            if direction_val == "ABOVE":
                dir_text = "above"
                cmp_symbol = "≥"
            elif direction_val == "BELOW":
                dir_text = "below"
                cmp_symbol = "≤"
            else:
                dir_text = str(getattr(alert.direction, "value", str(alert.direction))).lower()
                cmp_symbol = ""

            current_price_str = _fmt(current_price if current_price is not None else last_val)
            bid_str = _fmt(bid_val)
            ask_str = _fmt(ask_val)
            target_price_str = _fmt(getattr(alert, "target_price", None))

            msg_text = (
                f"📢 *Price Alert Triggered!*\n"
                f"Symbol: `{getattr(alert, 'symbol', norm_symbol)}`\n"
                f"Alert: {dir_text} {target_price_str} ({cmp_symbol} {target_price_str})\n"
                f"Current Price: `{current_price_str}`\n"
                f"BID: `{bid_str}`  |  ASK: `{ask_str}`\n"
                f"Alert ID: `{getattr(alert, 'id', '?')}`"
            )

            try:
                await update.message.reply_text(msg_text, parse_mode="Markdown")
            except Exception:
                logger.exception("Failed to send trigger message for newly-created triggered alert %s", getattr(alert, "id", "?"))
    except Exception:
        logger.exception("Error while preparing/sending triggered notice for alert %s", getattr(alert, "id", "?"))

    # 3) Send immediate charts for each timeframe using get_chart (which computes from_date)
    # Use the alert's stored timeframes (canonical tokens) if available — this avoids mismatch with chart generator.
    try:
        if getattr(alert, "timeframes", None):
            tfs_for_plot = [s.strip() for s in str(alert.timeframes).split(",") if s.strip()]
        else:
            tfs_for_plot = normalized_tfs
    except Exception:
        tfs_for_plot = normalized_tfs

    norm_symbol = normalize_symbol(symbol)
    for tf_token in tfs_for_plot:
        try:
            # Try requested / fallback TFs
            buf, interval_norm, used_tf = await _try_get_chart_with_fallback(loop, norm_symbol, tf_token, alert.target_price, outputsize=150)

            # ensure buffer readable from start
            try:
                buf.seek(0)
            except Exception:
                pass

            caption = f"⏱ Timeframe: {interval_norm}, Symbol: {symbol.upper()}"
            if used_tf != tf_token:
                caption += f" (requested {tf_token} — plotted {used_tf})"

            await update.message.reply_photo(
                photo=buf,
                filename=f"{symbol}_{interval_norm}.png",
                caption=caption
            )
        except Exception as e:
            # final failure after fallbacks
            logger.exception("Chart generation error for %s tf=%s (after fallbacks)", symbol, tf_token)
            # show the error message to the user but keep it friendly
            await update.message.reply_text(f"⚠️ Could not generate chart for {symbol} {tf_token}: {e}")

        await asyncio.sleep(INTER_CHART_DELAY)


handler = CommandHandler("alert", alert_command)
