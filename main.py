from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import models  # noqa: F401
from app.db.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.web.pages.admin import router as admin_pages_router
from app.web.data import fridge_items, get_themealdb_recipes, get_usda_foods
from app.web.layout import register_auth_middleware
from app.web.pages.alerts import router as alerts_pages_router
from app.web.pages.authentification import router as auth_pages_router
from app.web.pages.fridge import router as fridge_pages_router
from app.web.pages.home import router as home_pages_router
from app.web.pages.nutrition import router as nutrition_pages_router
from app.web.pages.products import router as products_pages_router
from app.web.pages.profile import router as profile_pages_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Fridge & Nutrition Coach")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(home_pages_router)
app.include_router(auth_pages_router)
app.include_router(fridge_pages_router)
app.include_router(products_pages_router)
app.include_router(nutrition_pages_router)
app.include_router(alerts_pages_router)
app.include_router(profile_pages_router)
app.include_router(admin_pages_router)
register_auth_middleware(app)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = FastAPI.openapi(app)

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Compatibility exports for the legacy test suite and existing imports.
__all__ = [
    "app",
    "fridge_items",
    "get_usda_foods",
    "get_themealdb_recipes",
]
