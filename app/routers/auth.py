from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import UserDB
from app.models.auth import UserCreate, UserLogin, Token
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token
from app.core.dependencies import get_current_user


router = APIRouter(prefix="/auth", tags=["Auth"])


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60,
    )


@router.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    hashed = hash_password(user.password)
    new_user = UserDB(email=user.email, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="Identifiants invalides")

    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Identifiants invalides")

    token = create_access_token({"sub": str(db_user.id)})
    set_auth_cookie(response, token)
    return Token(access_token=token)


@router.get("/me")
def me(user = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}