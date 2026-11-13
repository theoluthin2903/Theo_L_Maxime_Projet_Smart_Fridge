import os
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import UserDB
from app.models.auth import UserCreate, UserLogin, Token
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token
from app.core.dependencies import get_current_user
from app.core import rate_limit


router = APIRouter(prefix="/auth", tags=["Auth"])

INVALID_CREDENTIALS = "Identifiants invalides"
# Hash de référence : vérifié quand l'adresse n'existe pas, pour que la réponse prenne
# le même temps et ne révèle pas quelles adresses ont un compte.
_DUMMY_HASH = hash_password("smart-fridge-dummy-password")


def is_https(request: Request) -> bool:
    """HTTPS direct, ou derrière un proxy qui termine le TLS (Scalingo, Render…)."""
    if os.getenv("COOKIE_SECURE") in {"0", "1"}:
        return os.getenv("COOKIE_SECURE") == "1"
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or forwarded == "https"


def set_auth_cookie(request: Request, response: Response, token: str, remember_me: bool = False):
    cookie_options = {
        "key": "access_token",
        "value": token,
        "httponly": True,
        "samesite": "lax",
        # Secure : le cookie n'est envoyé qu'en HTTPS une fois le site en ligne.
        "secure": is_https(request),
    }

    # Sans « Rester connecté », le cookie est un cookie de session :
    # il disparaît lorsque le navigateur est complètement fermé.
    if remember_me:
        cookie_options["max_age"] = 60 * 60 * 24 * 30

    response.set_cookie(**cookie_options)


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
def login(user: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    wait = rate_limit.retry_after(request, user.email)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Trop de tentatives de connexion. Réessayez dans {max(1, wait // 60)} min.",
            headers={"Retry-After": str(wait)},
        )

    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    # Toujours une vérification de hash, que le compte existe ou non.
    password_ok = verify_password(user.password, db_user.hashed_password if db_user else _DUMMY_HASH)
    if not db_user or not password_ok:
        rate_limit.record_failure(request, user.email)
        raise HTTPException(status_code=400, detail=INVALID_CREDENTIALS)

    rate_limit.reset(request, user.email)
    token_lifetime = timedelta(days=30) if user.remember_me else timedelta(hours=12)
    token = create_access_token({"sub": str(db_user.id)}, expires_delta=token_lifetime)
    set_auth_cookie(request, response, token, remember_me=user.remember_me)
    return Token(access_token=token)


@router.get("/me")
def me(user = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}
