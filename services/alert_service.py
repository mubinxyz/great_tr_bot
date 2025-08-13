# services/alert_service.py

from datetime import datetime
from typing import Optional, Union
from models.alert import Alert, AlertDirection
from services.db_service import get_db
from utils.normalize_data import normalize_symbol
from utils.get_data import DataService

data_service = DataService()


def _extract_price(price_resp: Union[dict, float, int, None]) -> Optional[float]:
    """
    Normalize DataService.get_price output into a float price or None.
    Accepts:
      - dict with 'price' (or 'last', 'close', 'ask', 'bid')
      - plain numeric (float/int)
      - None -> returns None
    """
    if price_resp is None:
        return None
    if isinstance(price_resp, dict):
        # common keys to check, in order of preference
        for key in ("price", "last", "close", "ask", "bid", "last_price"):
            if key in price_resp and price_resp[key] is not None:
                try:
                    return float(price_resp[key])
                except (ValueError, TypeError):
                    continue
        # if dictionary contains a single numeric-like value, try to find it
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

    timeframes may be a list (e.g. ['1h','4h']) or a comma-separated string.
    """
    # normalize timeframes into comma-separated string
    if isinstance(timeframes, list):
        tf_str = ",".join([str(tf).strip() for tf in timeframes if str(tf).strip()])
    else:
        tf_str = str(timeframes or "").strip()

    # coerce target_price to float
    try:
        target_price = float(target_price)
    except Exception as e:
        raise ValueError(f"Invalid target_price: {target_price}") from e

    # Get current market price from DataService
    try:
        price_info = data_service.get_price(symbol)
        current_price = _extract_price(price_info)
        if current_price is None:
            raise RuntimeError(f"Failed to parse current price for {symbol} (response: {price_info})")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch price for {symbol}: {e}") from e

    # Determine direction and trigger status
    # If the target is greater than current price -> user waiting for price to go ABOVE target
    if target_price > current_price:
        direction = AlertDirection.ABOVE
        triggered = False
        triggered_at = None
    elif target_price < current_price:
        direction = AlertDirection.BELOW
        triggered = False
        triggered_at = None
    else:  # target exactly matches current price -> treat as triggered now
        direction = AlertDirection.ABOVE
        triggered = True
        triggered_at = datetime.utcnow()

    # Normalize symbol string
    try:
        normalized_symbol = normalize_symbol(symbol)
    except Exception:
        normalized_symbol = str(symbol).upper()

    # Persist to DB
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
    """
    Returns all alerts that have not yet been triggered.
    """
    with get_db() as db:
        return db.query(Alert).filter_by(triggered=False).all()


def mark_alert_triggered(alert_id: int):
    """
    Marks a given alert as triggered and sets triggered_at timestamp.
    """
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return None
        alert.triggered = True
        alert.triggered_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)
        return alert
