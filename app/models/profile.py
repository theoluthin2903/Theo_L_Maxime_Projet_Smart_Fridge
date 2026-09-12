from typing import Optional

from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    sex: Optional[str] = None
    activity: Optional[str] = None
    goal: Optional[str] = None


class ProfileOut(BaseModel):
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    sex: Optional[str] = None
    activity: Optional[str] = None
    goal: Optional[str] = None