from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "6448f6dc50e8e0dea04e4c5c1a9f42297903a8fe241b71e928729037cb96bbd9"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
