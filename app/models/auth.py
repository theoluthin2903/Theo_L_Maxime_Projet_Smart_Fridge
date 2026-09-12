from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: str
    password: str = Field(..., min_length=6)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
