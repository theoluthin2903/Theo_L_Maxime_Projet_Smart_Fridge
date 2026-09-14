from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./smartfridge.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_fridge_user_id_column():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "fridge_items" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("fridge_items")}
        if "user_id" not in columns:
            conn.execute(text("ALTER TABLE fridge_items ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"))


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


def run_startup_checks() -> None:
    """Run schema compatibility checks only when explicitly requested.

    The app should not mutate the SQLite database on import/startup. This is
    especially important for persistent local development DBs where sample rows
    or altered columns can be silently rewritten each launch.
    """
    if os.getenv("SMARTFRIDGE_RUN_MIGRATIONS", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    ensure_fridge_user_id_column()
    ensure_user_profile_columns()


import os
