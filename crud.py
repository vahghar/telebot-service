# crud.py
from sqlalchemy.orm import Session
import models
import schemas

def get_or_create_user(db: Session, user: schemas.UserCreate) -> tuple[models.User, bool]:
    """
    Gets a user by chat_id or creates a new one.
    Returns the user object and a boolean (True if created, False if existed).
    """
    db_user = db.query(models.User).filter(models.User.chat_id == user.chat_id).first()
    if db_user:
        return db_user, False  # User already existed
    
    db_user = models.User(chat_id=user.chat_id)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user, True  # User was created

def get_all_user_ids(db: Session) -> list[int]:
    """Retrieves a list of all user chat IDs."""
    # The result from the query is a list of tuples, e.g., [(123,), (456,)]
    # We use a list comprehension to flatten it into [123, 456]
    return [user_id for user_id, in db.query(models.User.chat_id).all()]

def remove_user(db: Session, chat_id: int) -> bool:
    """Removes a user by chat_id. Returns True if deleted, False if not found."""
    db_user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False