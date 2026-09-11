from fastapi import FastAPI
from app.db.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Fridge & Nutrition Coach")

app.include_router(auth_router)
app.include_router(profile_router)

@app.get("/")
def home():
    return {"message": "Bienvenue dans le Smart Fridge & Nutrition Coach !"}
