from models.user import User
from services.db_service import get_db

def get_or_create_user(chat_id, username=None, first_name=None, last_name=None):
    with get_db() as db:
        user = db.query(User).filter_by(chat_id=chat_id).first()
        if not user:
            user = User(
                chat_id=chat_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
