from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from services.db_service import SessionLocal
from models.alert import Alert
from models.user import User

async def list_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(chat_id=update.effective_chat.id).first()
        if not user:
            await update.message.reply_text("⚠️ You don't have any alerts set.")
            return

        alerts = session.query(Alert).filter_by(user_id=user.id).all()
        if not alerts:
            await update.message.reply_text("📭 No active alerts.")
            return

        keyboard = []
        text_lines = []

        for alert in alerts:
            # Example: EUR/USD ≥ 1.1234 (4h, 15m) — Above
            symbol_display = alert.symbol
            sign = "≥" if alert.direction == "above" else "≤"
            tf_str = ", ".join(alert.timeframes.split(","))
            text_lines.append(f"{symbol_display} {sign} {alert.target_price} ({tf_str}) — {alert.direction.capitalize()}")

            # Add delete button
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ Delete {symbol_display} {alert.target_price}",
                    callback_data=f"delete_alert:{alert.id}"
                )
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "\n".join(text_lines),
            reply_markup=reply_markup
        )
    finally:
        session.close()


async def delete_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    alert_id = int(query.data.split(":")[1])

    session = SessionLocal()
    try:
        alert = session.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            await query.edit_message_text("⚠️ Alert not found or already deleted.")
            return

        session.delete(alert)
        session.commit()

        await query.edit_message_text(f"🗑 Deleted alert for {alert.symbol} {alert.target_price}")
    finally:
        session.close()


list_alerts_handler = CommandHandler("listalerts", list_alerts_command)
delete_alert_handler = CallbackQueryHandler(delete_alert_callback, pattern=r"^delete_alert:\d+$")
