import getpass
import sys

from app.core.security import hash_password
from app.db.database import Base, engine, SessionLocal
from app.db.models import UserDB


def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else input("Email administrateur : ")).strip().lower()
    if not email:
        print("Email invalide.")
        raise SystemExit(1)

    password = getpass.getpass("Mot de passe administrateur (6 caractères minimum) : ")
    if len(password) < 6:
        print("Le mot de passe doit contenir au moins 6 caractères.")
        raise SystemExit(1)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.email == email).first()
        if user:
            user.hashed_password = hash_password(password)
            user.is_admin = 1
            db.commit()
            print(f"Le compte {email} est maintenant administrateur.")
        else:
            user = UserDB(email=email, hashed_password=hash_password(password), is_admin=1)
            db.add(user)
            db.commit()
            print(f"Compte administrateur créé : {email}")


if __name__ == "__main__":
    main()