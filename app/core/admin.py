from fastapi import HTTPException, Request
from jose import JWTError, jwt

from app.core.jwt import ALGORITHM, SECRET_KEY
from app.db.database import SessionLocal
from app.db.models import UserDB
from app.web.layout import get_token_from_request


def get_current_admin(request: Request) -> UserDB:
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=403, detail="Accès administrateur requis")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=403, detail="Accès administrateur requis")
        user_id = int(user_id)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Accès administrateur requis")

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user or not user.is_admin:
            raise HTTPException(status_code=403, detail="Accès administrateur requis")
        # Detach the ORM object before the session closes.
        db.expunge(user)
        return user
