from fastapi import FastAPI
from routers import auth

app = FastAPI(title="Smart Fridge & Nutrition Coach")

app.include_router(auth.router)

@app.get("/")
def home():
    return {"message": "Bienvenue dans le Smart Fridge & Nutrition Coach !"}
