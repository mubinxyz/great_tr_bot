# services/alert_service.py
from datetime import datetime
from models.alert import Alert, AlertDirection
from services.db_service import get_db
from services.twelvedata_service import TwelveDataService

td_service = TwelveDataService()

def create_alert(user_id: int, symbol: str, target_price: float, timeframes: list):
    """
    Create alert, determine direction by comparing current market price.
    Returns the created Alert instance (SQLAlchemy object).
    """
    # prepare timeframes string
    tf_str = ",".join(timeframes)

    # get current market price (may raise if TwelveData fails)
    current_price = td_service.get_price(symbol)

    if target_price > current_price:
        direction = AlertDirection.ABOVE
        triggered = False
        triggered_at = None
    elif target_price < current_price:
        direction = AlertDirection.BELOW
        triggered = False
        triggered_at = None
    else:  # equal -> treat as already hit
        direction = AlertDirection.ABOVE
        triggered = True
        triggered_at = datetime.utcnow()

    # store a normalized symbol string for clarity
    try:
        normalized_symbol = td_service.normalize_symbol(symbol)
    except Exception:
        normalized_symbol = symbol.upper()

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
    with get_db() as db:
        return db.query(Alert).filter_by(triggered=False).all()


def mark_alert_triggered(alert_id: int):
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return None
        alert.triggered = True
        alert.triggered_at = datetime.utcnow()
        db.commit()
        db.refresh(alert)
        return alert
