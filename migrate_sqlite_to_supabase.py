import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

ROOT = Path(__file__).resolve().parent
SQLITE_PATH = ROOT / "smartfridge.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not SQLITE_PATH.exists():
    raise SystemExit(f"ERREUR : {SQLITE_PATH.name} introuvable. Place ce script à la racine du projet.")
if not DATABASE_URL:
    raise SystemExit("ERREUR : DATABASE_URL absente du fichier .env.")
if "YOUR-PASSWORD" in DATABASE_URL or "PROJECT_REF" in DATABASE_URL:
    raise SystemExit("ERREUR : DATABASE_URL contient encore une valeur d'exemple.")

# SQLAlchemy + psycopg 3
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH.as_posix()}")
supabase_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

TABLES = ["users", "fridge_items", "admin_logs"]


def rows_as_dicts(conn, table_name):
    return [dict(row._mapping) for row in conn.execute(text(f'SELECT * FROM "{table_name}"'))]


def ensure_destination_tables():
    # Importe les modèles du projet pour créer exactement le schéma attendu.
    # Les INSERT de migration sont ensuite faits en SQL brut : les événements ORM
    # (ex. log automatique de création de compte) ne sont donc pas déclenchés.
    from app.db.models import Base
    Base.metadata.create_all(bind=supabase_engine)


def migrate_table(source_conn, dest_conn, table_name):
    source_rows = rows_as_dicts(source_conn, table_name)
    if not source_rows:
        print(f"- {table_name}: 0 ligne à migrer")
        return 0

    dest_columns = {c["name"] for c in inspect(dest_conn).get_columns(table_name)}
    inserted = 0

    for row in source_rows:
        row = {k: v for k, v in row.items() if k in dest_columns}
        if "id" not in row:
            continue

        # Si cet ID existe déjà sur Supabase, on ne l'écrase pas.
        exists = dest_conn.execute(
            text(f'SELECT 1 FROM "{table_name}" WHERE id = :id'), {"id": row["id"]}
        ).first()
        if exists:
            continue

        # users.email est UNIQUE : évite aussi un doublon d'adresse mail.
        if table_name == "users" and row.get("email"):
            email_exists = dest_conn.execute(
                text('SELECT 1 FROM "users" WHERE email = :email'), {"email": row["email"]}
            ).first()
            if email_exists:
                continue

        columns = list(row.keys())
        col_sql = ", ".join(f'"{c}"' for c in columns)
        val_sql = ", ".join(f':{c}' for c in columns)
        dest_conn.execute(
            text(f'INSERT INTO "{table_name}" ({col_sql}) VALUES ({val_sql})'), row
        )
        inserted += 1

    print(f"- {table_name}: {inserted}/{len(source_rows)} ligne(s) ajoutée(s)")
    return inserted


def reset_postgres_sequence(conn, table_name):
    # Aligne l'auto-incrément PostgreSQL après conservation des IDs SQLite.
    conn.execute(text(f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', 'id'),
            COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 1),
            EXISTS (SELECT 1 FROM \"{table_name}\")
        )
    """))


def main():
    print("Smart Fridge - migration SQLite -> Supabase")
    print(f"Source : {SQLITE_PATH.name}")
    print("Destination : Supabase PostgreSQL\n")

    with supabase_engine.connect() as test_conn:
        test_conn.execute(text("SELECT 1"))
    print("Connexion Supabase : OK")

    ensure_destination_tables()
    print("Tables Supabase : OK\n")

    src_tables = set(inspect(sqlite_engine).get_table_names())
    missing = [t for t in TABLES if t not in src_tables]
    if missing:
        raise SystemExit("ERREUR : table(s) absente(s) de SQLite : " + ", ".join(missing))

    total = 0
    # Une transaction unique : en cas d'erreur, Supabase revient à l'état précédent.
    with sqlite_engine.connect() as source_conn, supabase_engine.begin() as dest_conn:
        for table in TABLES:
            total += migrate_table(source_conn, dest_conn, table)
        for table in TABLES:
            reset_postgres_sequence(dest_conn, table)

    print(f"\nMigration terminée : {total} ligne(s) ajoutée(s).")
    print("Le fichier smartfridge.db n'a pas été modifié ni supprimé.")
    print("Tu peux maintenant lancer : uvicorn main:app --reload")


if __name__ == "__main__":
    main()
