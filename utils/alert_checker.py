# utils/alert_checker.py
import asyncio
import functools
import logging
from collections import defaultdict
from typing import Optional, Dict, Any

from utils.get_data import get_price
from services.alert_service import get_pending_alerts, mark_alert_triggered
from services.chart_service import get_chart
from models.alert import AlertDirection
from utils.normalize_data import normalize_timeframe

logger = logging.getLogger(__name__)

# default timeframe token used when alert does not have timeframes stored
DEFAULT_TF = "60"
# default outputsize used when requesting charts from chart_service
DEFAULT_OUTPUTSIZE = 150


def _extract_price(price_resp) -> Optional[float]:
    if price_resp is None:
        return None

    if isinstance(price_resp, dict):
        for key in ("price", "last", "close", "ask", "bid", "last_price"):
            if key in price_resp and price_resp[key] is not None:
                try:
                    return float(price_resp[key])
                except (ValueError, TypeError):
                    continue
        for v in price_resp.values():
            try:
                return float(v)
            except Exception:
                continue
        return None

    try:
        return float(price_resp)
    except Exception:
        return None


def _format_price_val(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.6f}"
    except Exception:
        return str(val)


def _to_plain_alert(alert_obj_or_dict: Any) -> Dict[str, Any]:
    if isinstance(alert_obj_or_dict, dict):
        d = dict(alert_obj_or_dict)
        try:
            if d.get("target_price") is not None:
                d["target_price"] = float(d["target_price"])
        except Exception:
            pass
        return d

    d = {}
    try:
        d["id"] = getattr(alert_obj_or_dict, "id", None)
        d["symbol"] = getattr(alert_obj_or_dict, "symbol", None)
        tp = getattr(alert_obj_or_dict, "target_price", None)
        d["target_price"] = float(tp) if tp is not None else None
        d["timeframes"] = getattr(alert_obj_or_dict, "timeframes", None)
        dir_attr = getattr(alert_obj_or_dict, "direction", None)
        try:
            d["direction"] = getattr(dir_attr, "value", str(dir_attr))
        except Exception:
            d["direction"] = str(dir_attr)
        try:
            user = getattr(alert_obj_or_dict, "user", None)
            if user is not None:
                d["user_chat_id"] = getattr(user, "chat_id", None)
            else:
                d["user_chat_id"] = getattr(alert_obj_or_dict, "user_id", None)
        except Exception:
            d["user_chat_id"] = getattr(alert_obj_or_dict, "user_id", None)
        d["user_id"] = getattr(alert_obj_or_dict, "user_id", None)
        ta = getattr(alert_obj_or_dict, "triggered_at", None)
        d["triggered_at"] = ta.isoformat() if ta is not None else None
    except Exception:
        return {"id": getattr(alert_obj_or_dict, "id", None)}
    return d


async def check_alerts_job(context):
    try:
        alerts = get_pending_alerts()
    except Exception as e:
        logger.exception("Failed to load pending alerts: %s", e)
        return

    if not alerts:
        return

    # Group alerts by normalized symbol to fetch price once per symbol
    alerts_by_symbol = defaultdict(list)
    for alert in alerts:
        try:
            sym = (alert.symbol or "").strip().upper()
        except Exception:
            sym = str(getattr(alert, "symbol", "")).strip().upper()
        alerts_by_symbol[sym].append(alert)

    loop = asyncio.get_running_loop()

    for symbol, symbol_alerts in alerts_by_symbol.items():
        if not symbol:
            logger.warning("[AlertChecker] Encountered alert with empty symbol; skipping %d alerts", len(symbol_alerts))
            continue

        # fetch current price once for this symbol
        try:
            price_resp = await loop.run_in_executor(None, functools.partial(get_price, symbol))
        except Exception as e:
            logger.warning("[AlertChecker] Price fetch failed for %s (skipping %d alerts): %s", symbol, len(symbol_alerts), e)
            continue

        current_price = _extract_price(price_resp)
        if current_price is None:
            logger.warning("[AlertChecker] Could not parse price for %s; skipping %d alerts", symbol, len(symbol_alerts))
            continue

        bid_val = None
        ask_val = None
        last_val = None
        if isinstance(price_resp, dict):
            last_val = price_resp.get("price") or price_resp.get("last") or price_resp.get("close") or price_resp.get("last_price")
            bid_val = price_resp.get("bid")
            ask_val = price_resp.get("ask")

        for alert in symbol_alerts:
            try:
                # read target price robustly
                try:
                    target_price = float(getattr(alert, "target_price", None))
                except Exception:
                    try:
                        target_price = float(alert.get("target_price"))
                    except Exception:
                        target_price = None

                # direction detection
                dir_attr = getattr(alert, "direction", None)
                try:
                    dstr = getattr(dir_attr, "value", str(dir_attr)).upper()
                except Exception:
                    dstr = str(dir_attr).upper() if dir_attr is not None else ""

                is_above = (dstr == getattr(AlertDirection.ABOVE, "value", "ABOVE") or dstr == "ABOVE")
                is_below = (dstr == getattr(AlertDirection.BELOW, "value", "BELOW") or dstr == "BELOW")

                if not (is_above or is_below) and target_price is not None:
                    is_above = target_price > current_price
                    is_below = target_price < current_price

                if target_price is None:
                    logger.warning("[AlertChecker] Alert %s has invalid target_price; skipping", getattr(alert, "id", "?"))
                    continue

                triggered_now = False
                if is_above and current_price >= float(target_price):
                    triggered_now = True
                elif is_below and current_price <= float(target_price):
                    triggered_now = True

                if not triggered_now:
                    continue

                # mark alert triggered in DB
                try:
                    updated_alert_raw = await loop.run_in_executor(None, functools.partial(mark_alert_triggered, alert.id))
                    updated_alert = updated_alert_raw if updated_alert_raw else alert
                except Exception as e:
                    logger.exception("[AlertChecker] Failed to mark alert %s as triggered: %s", getattr(alert, "id", "?"), e)
                    updated_alert = alert

                alert_dict = _to_plain_alert(updated_alert)

                # resolve chat id
                chat_id = alert_dict.get("user_chat_id") or alert_dict.get("user_id")
                if not chat_id:
                    logger.warning("[AlertChecker] No chat_id for alert %s - cannot notify user", alert_dict.get("id", "?"))
                    continue

                # build message
                dir_val = str(alert_dict.get("direction") or "").upper()
                if dir_val == getattr(AlertDirection.ABOVE, "value", "ABOVE") or dir_val == "ABOVE":
                    dir_text = "above"
                    cmp_symbol = "≥"
                elif dir_val == getattr(AlertDirection.BELOW, "value", "BELOW") or dir_val == "BELOW":
                    dir_text = "below"
                    cmp_symbol = "≤"
                else:
                    dir_text = dir_val.lower() if dir_val else ""
                    cmp_symbol = ""

                current_price_str = _format_price_val(current_price if current_price is not None else last_val)
                bid_str = _format_price_val(bid_val)
                ask_str = _format_price_val(ask_val)
                target_price_str = _format_price_val(alert_dict.get("target_price"))

                msg_text = (
                    f"📢 *Price Alert Triggered!*\n"
                    f"Symbol: `{alert_dict.get('symbol')}`\n"
                    f"Alert: {dir_text} {target_price_str} ({cmp_symbol} {target_price_str})\n"
                    f"Current Price: `{current_price_str}`\n"
                    f"BID: `{bid_str}`  |  ASK: `{ask_str}`\n"
                    f"Alert ID: `{alert_dict.get('id','?')}`"
                )

                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg_text, parse_mode="Markdown")
                except Exception as e:
                    logger.exception("[AlertChecker] Failed to send trigger message for alert %s to %s: %s", alert_dict.get("id", "?"), chat_id, e)

                # use stored timeframes or default
                tfs_raw = alert_dict.get("timeframes") or DEFAULT_TF
                tfs = [s.strip() for s in str(tfs_raw).split(",") if s.strip()]
                if not tfs:
                    tfs = [DEFAULT_TF]

                # generate/send charts using chart_service.get_chart
                for tf in tfs:
                    try:
                        try:
                            tf_for_chart = normalize_timeframe(tf)
                        except Exception:
                            tf_for_chart = tf

                        # IMPORTANT: use an integer outputsize (not None). None caused compute_from_date to return None
                        call_plot = functools.partial(
                            get_chart,
                            symbol=alert_dict.get("symbol"),
                            timeframe=tf_for_chart,
                            alert_price=alert_dict.get("target_price"),
                            from_date=None,
                            to_date=None,
                            outputsize=DEFAULT_OUTPUTSIZE,
                        )

                        buf, interval_minutes = await loop.run_in_executor(None, call_plot)

                        try:
                            buf.seek(0)
                        except Exception:
                            pass

                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=buf,
                            filename=f"{alert_dict.get('symbol')}_{interval_minutes}.png",
                            caption=f"⏱ Timeframe: {interval_minutes}, Symbol: {alert_dict.get('symbol')}"
                        )
                    except Exception as e:
                        # handle chart errors gracefully and inform user
                        logger.exception("[AlertChecker] Failed to generate/send chart for alert %s tf=%s: %s", alert_dict.get("id", "?"), tf, e)

                        # Friendly message to user; if it's a TypeError caused by None * int, provide a hint
                        err_msg = str(e)
                        if "NoneType" in err_msg and "*" in err_msg:
                            user_msg = f"⚠️ Could not generate chart for {alert_dict.get('symbol')} timeframe {tf}: chart service returned no data (internal computation failed)."
                            logger.debug("Likely cause: outputsize or compute_from_date returned None. Consider checking chart provider / supported timeframes.")
                        else:
                            user_msg = f"⚠️ Could not generate chart for {alert_dict.get('symbol')} timeframe {tf}: {e}"

                        try:
                            await context.bot.send_message(chat_id=chat_id, text=user_msg)
                        except Exception:
                            logger.exception("[AlertChecker] Also failed to notify user about chart generation error for alert %s", alert_dict.get("id", "?"))

            except Exception as e:
                logger.exception("[AlertChecker] Unexpected error when processing alert %s: %s", getattr(alert, "id", "?"), e)
