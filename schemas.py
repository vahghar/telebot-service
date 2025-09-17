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

class RebalanceEventBase(BaseModel):
    rebalance_id: str
    transaction_hash: str

class RebalanceEventCreate(RebalanceEventBase):
    pass

class RebalanceEvent(RebalanceEventBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True
