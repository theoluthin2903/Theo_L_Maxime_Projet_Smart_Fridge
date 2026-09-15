from sqlalchemy import text

from app.db.database import engine

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database(), current_user"))
        database, user = result.one()
        print("Connexion Supabase OK")
        print(f"Base : {database}")
        print(f"Utilisateur : {user}")
except Exception as exc:
    print("Connexion Supabase impossible :")
    print(exc)
    raise SystemExit(1)
