# handlers/listalerts.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from services.db_service import SessionLocal
from models.alert import Alert
from models.user import User

def _direction_display(alert):
    # Works whether alert.direction is an Enum or plain string
    try:
        return getattr(alert.direction, "value", str(alert.direction)).capitalize()
    except Exception:
        return str(alert.direction).capitalize()

def build_alerts_message_and_keyboard(alerts):
    """
    Given a list of Alert objects, return (text, InlineKeyboardMarkup).
    """
    if not alerts:
        return "📭 No active alerts.", None

    lines = []
    keyboard = []
    for alert in alerts:
        symbol_display = alert.symbol
        # If direction is enum or string, this handles both
        direction_display = _direction_display(alert)
        # show sign for clarity
        sign = "≥" if str(alert.direction).lower().startswith("above") else "≤"
        tf_str = ", ".join(alert.timeframes.split(","))
        lines.append(f"{symbol_display} {sign} {alert.target_price} ({tf_str}) — {direction_display}")

        # add a delete button per-alert
        keyboard.append([
            InlineKeyboardButton(
                text=f"❌ Delete {symbol_display} {alert.target_price}",
                callback_data=f"delete_alert:{alert.id}"
            )
        ])

    text = "\n".join(lines)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    return text, reply_markup

async def list_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(chat_id=update.effective_chat.id).first()
        if not user:
            await update.message.reply_text("📭 You don't have any alerts set.")
            return

        alerts = session.query(Alert).filter_by(user_id=user.id).all()
        text, reply_markup = build_alerts_message_and_keyboard(alerts)

        if reply_markup:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text)
    finally:
        session.close()

async def delete_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # acknowledge callback promptly

    # Parse alert id
    try:
        alert_id = int(query.data.split(":")[1])
    except Exception:
        await query.edit_message_text("⚠️ Invalid request.")
        return

    session = SessionLocal()
    try:
        alert = session.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            # Re-render remaining alerts if possible
            # (maybe the alert was already deleted elsewhere)
            user = session.query(User).filter_by(chat_id=query.from_user.id).first()
            if not user:
                await query.edit_message_text("⚠️ Alert not found.")
                return
            remaining = session.query(Alert).filter_by(user_id=user.id).all()
            text, keyboard = build_alerts_message_and_keyboard(remaining)
            if keyboard:
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                await query.edit_message_text("📭 No active alerts.")
            return

        # Delete the alert
        user_id = alert.user_id
        session.delete(alert)
        session.commit()

        # After deleting, re-query remaining alerts for the same user
        remaining = session.query(Alert).filter_by(user_id=user_id).all()
        text, keyboard = build_alerts_message_and_keyboard(remaining)

        if keyboard:
            # Edit the original message to show the updated list and keyboard
            await query.edit_message_text(text, reply_markup=keyboard)
        else:
            await query.edit_message_text("🗑 Deleted. 📭 No active alerts.")
    finally:
        session.close()

# Handler instances (import these into your bot setup)
list_alerts_handler = CommandHandler("listalerts", list_alerts_command)
delete_alert_handler = CallbackQueryHandler(delete_alert_callback, pattern=r"^delete_alert:\d+$")
