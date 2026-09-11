from pydantic import BaseModel

class UserProfile(BaseModel):
    age: int
    weight: float
    height: float
    sex: str
    objective: str
