from sqlalchemy import Column, Float, Integer, String
from app.db.database import Base


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    age = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    sex = Column(String, nullable=True)
    activity = Column(String, nullable=True)
    goal = Column(String, nullable=True)


class FridgeItemDB(Base):
    __tablename__ = "fridge_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    expiration_date = Column(String, default="")
    category = Column(String, default="")
    notes = Column(String, default="")