import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^\s@<>\"']+@[^\s@<>\"']+\.[^\s@<>\"']+$")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise ValueError("Adresse e-mail invalide")
    return email


class UserCreate(BaseModel):
    email: str
    # 8 caractères minimum à l'inscription ; 128 maximum pour éviter un hachage interminable.
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Le mot de passe doit contenir au moins une lettre et un chiffre")
        return value


class UserLogin(BaseModel):
    email: str
    # Pas de règle de robustesse ici : les comptes créés avant la règle des 8 caractères doivent pouvoir se connecter.
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return value.strip().lower()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
