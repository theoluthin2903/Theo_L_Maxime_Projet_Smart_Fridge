import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Supabase fournit une URL PostgreSQL. Chaque développeur la place dans son
# propre fichier .env (ce fichier ne doit jamais être envoyé sur GitHub).
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smartfridge.db")

# SQLAlchemy 2 + psycopg 3 : accepte aussi directement l'URL copiée depuis
# Supabase qui commence par postgresql://.
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine_kwargs = {"pool_pre_ping": True}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_fridge_user_id_column():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "fridge_items" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("fridge_items")}
        if "user_id" not in columns:
            conn.execute(text(
                "ALTER TABLE fridge_items ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
            ))


def ensure_user_profile_columns():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "users" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("users")}
        new_columns = {
            "age": "INTEGER",
            "weight": "FLOAT",
            "height": "FLOAT",
            "sex": "VARCHAR",
            "activity": "VARCHAR",
            "goal": "VARCHAR",
            "is_admin": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, col_type in new_columns.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {col_type}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


ensure_fridge_user_id_column()
ensure_user_profile_columns()
