from sqlalchemy.orm import Session
from ..db import User, Setting, Message, Memory, Conversation

class MemoryService:
    def get_user_profile(self, db: Session, user_id: int = 1) -> dict:
        """Retrieve user profile key-values."""
        memories = db.query(Memory).filter(Memory.user_id == user_id).all()
        profile = {m.key: m.value for m in memories}
        # Include default user name
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            profile["name"] = user.name
        return profile

    def update_user_profile(self, db: Session, key: str, value: str, user_id: int = 1):
        """Save a piece of knowledge/profile data to database memory."""
        # Update user name if key is name
        if key == "name":
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.name = value
                db.commit()
                return

        existing = db.query(Memory).filter(Memory.user_id == user_id, Memory.key == key).first()
        if existing:
            existing.value = value
        else:
            db.add(Memory(user_id=user_id, key=key, value=value))
        db.commit()

    def get_settings(self, db: Session) -> dict:
        """Fetch all global configuration settings."""
        settings = db.query(Setting).all()
        return {s.key: s.value for s in settings}

    def set_setting(self, db: Session, key: str, value: str):
        """Update or insert a setting."""
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(Setting(key=key, value=value))
        db.commit()

    def get_recent_context(self, db: Session, conversation_id: str, limit: int = 10) -> list[dict]:
        """Fetch the list of recent messages formatted for context injection."""
        messages = db.query(Message).filter(Message.conversation_id == conversation_id)\
                     .order_by(Message.created_at.desc()).limit(limit).all()
        # Sort in chronological order
        messages.reverse()
        return [{"role": m.sender, "content": m.content} for m in messages]
