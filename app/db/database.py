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
