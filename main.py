from fastapi import FastAPI
from app.db.database import Base, engine
from app.routers.auth import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)


app = FastAPI(title="Smart Fridge & Nutrition Coach")

app.include_router(auth_router)

@app.get("/")
def home():
    return {"message": "Bienvenue dans le Smart Fridge & Nutrition Coach !"}



def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    
    openapi_schema = FastAPI.openapi(app)

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
