# services/alert_service.py
from datetime import datetime
from typing import Optional, Union
import logging

from models.alert import Alert, AlertDirection
from services.db_service import get_db
from utils.normalize_data import normalize_symbol
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


def create_alert(user_id: int, symbol: str, target_price: Union[float, str], timeframes: Union[list, str]):
    """
    Create an alert and determine direction by comparing current market price.
    Returns the created Alert instance (SQLAlchemy object).
    timeframes may be a list (e.g. ['1','60']) or a comma-separated string.
    """
    # Normalize timeframes into comma-separated string
    if isinstance(timeframes, list):
        tf_str = ",".join([str(tf).strip() for tf in timeframes if str(tf).strip()])
    else:
        tf_str = str(timeframes or "").strip()

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


def mark_alert_triggered(alert_id: int):
    """Mark alert as triggered and set timestamp."""
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return None
        alert.triggered = True
        alert.triggered_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)
        return alert
