# schemas.py
from pydantic import BaseModel
import datetime

class UserBase(BaseModel):
    chat_id: int

class UserCreate(UserBase):
    pass

class User(UserBase):
    created_at: datetime.datetime

    class Config:
        from_attributes = True