from datetime import datetime

from sqlalchemy import Column, Float, Integer, String, event

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
    is_admin = Column(Integer, nullable=False, default=0)


class FridgeItemDB(Base):
    __tablename__ = "fridge_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    expiration_date = Column(String, default="")
    category = Column(String, default="")
    notes = Column(String, default="")


class AdminLogDB(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    # 0 = système / action automatique (ex. création d'un compte utilisateur).
    admin_user_id = Column(Integer, nullable=False, index=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    details = Column(String, nullable=True)
    created_at = Column(String, nullable=False)


# Journalise automatiquement toutes les créations de comptes, y compris celles
# réalisées par le formulaire d'inscription normal du projet.
@event.listens_for(UserDB, "after_insert")
def log_user_creation(mapper, connection, target):
    connection.execute(
        AdminLogDB.__table__.insert().values(
            admin_user_id=0,
            action="Compte créé",
            target=f"#{target.id}",
            details=(target.email or "") + (" • administrateur" if target.is_admin else ""),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
