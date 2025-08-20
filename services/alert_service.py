# services/alert_service.py
from datetime import datetime
from typing import Optional, Union, Dict, Any
import logging

from sqlalchemy import func

from models.alert import Alert, AlertDirection
from services.db_service import get_db
from utils.normalize_data import normalize_symbol, normalize_timeframe
from utils.get_data import get_price  # use top-level function

logger = logging.getLogger(__name__)

# --- helpers ---
def _extract_price(price_resp: Union[dict, float, int, None]) -> Optional[float]:
    """
    Normalize get_price output into a float price or None.
    Accepts:
      - dict with 'price' (or 'last', 'close', 'ask', 'bid')
      - plain numeric (float/int)
      - None -> returns None
    """
    if price_resp is None:
        return None
    if isinstance(price_resp, dict):
        for key in ("price", "last", "close", "ask", "bid", "last_price"):
            if key in price_resp and price_resp[key] is not None:
                try:
                    return float(price_resp[key])
                except (ValueError, TypeError):
                    continue
        # fallback: try any numeric-like value
        for v in price_resp.values():
            try:
                return float(v)
            except Exception:
                continue
        return None
    # numeric-like
    try:
        return float(price_resp)
    except (ValueError, TypeError):
        return None


def _canonicalize_timeframes(timeframes: Union[list, str]) -> str:
    """
    Convert timeframes (list or comma-separated string) into a canonical,
    order-insensitive, comma-joined string, *using normalize_timeframe*
    so stored tokens match what charting expects.

    Example:
      ['1', '60'] -> '1,60'  (after normalize_timeframe)
      '60,1'       -> '1,60'
      '' or []     -> ''
    """
    if timeframes is None:
        return ""
    if isinstance(timeframes, list):
        parts = [str(t).strip() for t in timeframes if str(t).strip()]
    else:
        parts = [p.strip() for p in str(timeframes or "").split(",") if p.strip()]

    normalized_parts = []
    for p in parts:
        try:
            # use normalize_timeframe so '1', '1m', '60' etc. are converted to canonical token
            nf = normalize_timeframe(p)
            normalized_parts.append(str(nf))
        except Exception:
            # if normalization fails, keep the original token trimmed
            normalized_parts.append(p)

    # remove duplicates and sort deterministically (shorter first then lexicographic)
    unique_sorted = sorted(set(normalized_parts), key=lambda x: (len(x), x))
    return ",".join(unique_sorted)


def create_alert(user_id: int, symbol: str, target_price: Union[float, str], timeframes: Union[list, str]):
    """
    Create an alert and determine direction by comparing current market price.
    Returns the created Alert instance (SQLAlchemy object).

    Duplicate prevention:
      - If a pending (triggered=False) alert already exists for the same
        user_id, normalized symbol, target_price (within epsilon) and the
        same canonicalized timeframes, the existing alert is returned instead
        of creating a new row.

    timeframes may be a list (e.g. ['1','60']) or a comma-separated string.
    """
    # Normalize timeframes into canonical comma-separated string (order-insensitive)
    tf_str = _canonicalize_timeframes(timeframes)

    # coerce target_price
    try:
        target_price = float(target_price)
    except Exception as e:
        raise ValueError(f"Invalid target_price: {target_price}") from e

    # Normalize symbol early and use normalized form for price fetching & storage
    try:
        normalized_symbol = normalize_symbol(symbol)
    except Exception:
        normalized_symbol = str(symbol).upper()

    # Duplicate check tolerance
    EPSILON = 1e-8

    # Check for duplicate pending alert (same user, symbol, price (within EPSILON), timeframes, not yet triggered)
    try:
        with get_db() as db:
            existing = (
                db.query(Alert)
                .filter(
                    Alert.user_id == user_id,
                    Alert.symbol == normalized_symbol,
                    func.abs(Alert.target_price - float(target_price)) < EPSILON,
                    Alert.timeframes == tf_str,
                    Alert.triggered == False,
                )
                .first()
            )
            if existing:
                logger.info(
                    "Duplicate alert detected for user_id=%s symbol=%s price=%s tfs=%s — returning existing alert id=%s",
                    user_id, normalized_symbol, target_price, tf_str, existing.id
                )
                # refresh to be safe and mark transient flag for caller
                db.refresh(existing)
                try:
                    setattr(existing, "_is_duplicate", True)
                except Exception:
                    pass
                return existing
    except Exception:
        # If DB duplicate-check fails for some reason, log and continue to create alert
        logger.exception("Failed to check for duplicate alert; proceeding to create new one")

    # Get current market price
    try:
        price_info = get_price(normalized_symbol)
        logger.debug("get_price(%s) -> %s", normalized_symbol, price_info)
        current_price = _extract_price(price_info)
        if current_price is None:
            raise RuntimeError(f"Failed to parse current price for {normalized_symbol} (response: {price_info})")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch price for {normalized_symbol}: {e}") from e

    # Determine direction and trigger status
    if target_price > current_price:
        direction = AlertDirection.ABOVE
        triggered = False
        triggered_at = None
    elif target_price < current_price:
        direction = AlertDirection.BELOW
        triggered = False
        triggered_at = None
    else:
        # equal -> treat as triggered now
        direction = AlertDirection.ABOVE
        triggered = True
        triggered_at = datetime.utcnow()

    # Persist
    with get_db() as db:
        alert = Alert(
            user_id=user_id,
            symbol=normalized_symbol,
            target_price=float(target_price),
            direction=direction,
            timeframes=tf_str,
            triggered=triggered,
            triggered_at=triggered_at
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert


def get_pending_alerts():
    """Return all alerts that have not yet been triggered."""
    with get_db() as db:
        return db.query(Alert).filter_by(triggered=False).all()


def mark_alert_triggered(alert_id: int) -> Optional[Dict[str, Any]]:
    """
    Mark alert as triggered and set timestamp.

    Returns a plain dict with primitive values (avoids returning ORM objects across threads).
    """
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return None

        alert.triggered = True
        alert.triggered_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)

        # Try to safely resolve user.chat_id without returning ORM relationship objects
        user_chat_id = None
        try:
            # Accessing alert.user may raise if relationship is not configured/loaded; guard it
            if getattr(alert, "user", None) is not None:
                user_chat_id = getattr(alert.user, "chat_id", None)
        except Exception:
            user_chat_id = None

        return {
            "id": alert.id,
            "symbol": alert.symbol,
            "target_price": float(alert.target_price) if alert.target_price is not None else None,
            "timeframes": alert.timeframes,
            "direction": getattr(alert.direction, "value", str(alert.direction)),
            "user_chat_id": user_chat_id,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at is not None else None,
        }
