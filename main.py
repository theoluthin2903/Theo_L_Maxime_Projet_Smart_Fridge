from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException

from app.db import models  # noqa: F401
from app.db.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.web.pages.admin import router as admin_pages_router
from app.web.data import fridge_items, get_themealdb_recipes, get_usda_foods
from app.web.layout import register_auth_middleware, render_page
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


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    body = """
        <section class="mx-auto flex min-h-[70vh] max-w-2xl items-center justify-center">
            <div class="w-full rounded-3xl border border-green-100 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800 md:p-12">
                <div class="text-7xl" aria-hidden="true">🧊</div>
                <p class="mt-5 text-sm font-black uppercase tracking-[0.22em] text-pink-500">Erreur 404</p>
                <h1 class="mt-2 text-3xl font-black text-slate-900 dark:text-white md:text-4xl">Page introuvable</h1>
                <p class="mx-auto mt-4 max-w-lg text-slate-500 dark:text-slate-300">
                    L'adresse demandée n'existe pas ou la page a peut-être été déplacée.
                </p>
                <a href="/" class="mt-7 inline-flex rounded-xl bg-pink-500 px-6 py-3 font-bold text-white shadow-sm transition hover:bg-pink-600">
                    🏠 Retour à l'accueil
                </a>
            </div>
        </section>
    """
    response = render_page("Erreur 404", "", body, request)
    response.status_code = 404
    return response


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    body = """
        <section class="mx-auto flex min-h-[70vh] max-w-2xl items-center justify-center">
            <div class="w-full rounded-3xl border border-green-100 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800 md:p-12">
                <div class="text-7xl" aria-hidden="true">🛠️</div>
                <p class="mt-5 text-sm font-black uppercase tracking-[0.22em] text-pink-500">Erreur 500</p>
                <h1 class="mt-2 text-3xl font-black text-slate-900 dark:text-white md:text-4xl">Une erreur est survenue</h1>
                <p class="mx-auto mt-4 max-w-lg text-slate-500 dark:text-slate-300">
                    Smart Fridge a rencontré un problème inattendu. Réessaie dans quelques instants.
                </p>
                <a href="/" class="mt-7 inline-flex rounded-xl bg-pink-500 px-6 py-3 font-bold text-white shadow-sm transition hover:bg-pink-600">
                    🏠 Retour à l'accueil
                </a>
            </div>
        </section>
    """
    response = render_page("Erreur 500", "", body, request)
    response.status_code = 500
    return response


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
__all__ = [
    "app",
    "fridge_items",
    "get_usda_foods",
    "get_themealdb_recipes",
]
