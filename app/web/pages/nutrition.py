from datetime import date
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt
from sqlalchemy import func

from app.core.jwt import ALGORITHM, SECRET_KEY
from app.core.metabolism import compute_bmr_tdee
from app.db.database import SessionLocal
from app.db.models import NutritionIntakeDB, RecipeLeftoverDB, UserDB
from app.web.layout import get_token_from_request, require_auth, render_page

router = APIRouter()


def get_user_id(request: Request):
    token = get_token_from_request(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id is not None else None
    except (JWTError, ValueError, TypeError):
        return None


def progress(value, target):
    if not target or target <= 0:
        return 0
    return min(round((value / target) * 100), 100)


def stat_card(title, value, unit, percent, target=0):
    remaining = max(round(target - value), 0) if target else 0
    remaining_html = f'<p class="mt-1 text-xs text-slate-400">Reste {remaining} {unit}</p>' if target else ""
    return f"""
    <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p class="text-sm text-slate-500 dark:text-slate-300">{title}</p>
        <p class="mt-2 text-3xl font-bold text-slate-800 dark:text-white">{round(value)} <span class="text-base font-normal">{unit}</span></p>
        <div class="mt-4 h-3 rounded-full bg-slate-200 dark:bg-slate-700">
            <div class="h-3 rounded-full bg-green-600" style="width: {percent}%"></div>
        </div>
        <p class="mt-2 text-sm text-slate-500 dark:text-slate-300">{percent}% de l'objectif</p>
        {remaining_html}
    </div>
    """


@router.get("/nutrition", response_class=HTMLResponse)
def nutrition_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    today = date.today().isoformat()

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None
        intakes = (
            db.query(NutritionIntakeDB)
            .filter(
                NutritionIntakeDB.user_id == int(user_id),
                NutritionIntakeDB.consumed_at.like(f"{today}%"),
            )
            .order_by(NutritionIntakeDB.id.desc())
            .all()
            if user_id else []
        )
        leftovers = (
            db.query(RecipeLeftoverDB)
            .filter(RecipeLeftoverDB.user_id == int(user_id), RecipeLeftoverDB.remaining_percent > 0)
            .all()
            if user_id else []
        )

    nutrition = None
    if user and all([user.age is not None, user.weight is not None, user.height is not None, user.sex, user.activity, user.goal]):
        nutrition = compute_bmr_tdee(user)

    total_calories = sum(float(x.calories or 0) for x in intakes)
    total_proteins = sum(float(x.proteines or 0) for x in intakes)
    total_carbs = sum(float(x.glucides or 0) for x in intakes)
    total_fat = sum(float(x.lipides or 0) for x in intakes)

    if nutrition:
        target_calories = nutrition["target_calories"]
        target_proteins = nutrition["macros"]["proteins_g"]
        target_carbs = nutrition["macros"]["carbs_g"]
        target_fat = nutrition["macros"]["fats_g"]
        profile_block = f"""
        <div class="rounded-2xl border border-green-100 bg-green-50 p-6 dark:border-slate-700 dark:bg-slate-800">
            <div class="flex flex-wrap items-center justify-between gap-3">
                <div><h2 class="text-xl font-bold text-slate-800 dark:text-white">🎯 Guide nutritif du jour</h2>
                <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">Objectif calculé depuis votre profil. Ajoutez ce que vous mangez depuis la page Recettes.</p></div>
                <a href="/recipes" class="rounded-xl bg-green-700 px-4 py-2 font-semibold text-white hover:bg-green-800">🍽️ Choisir une recette</a>
            </div>
            <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><p class="text-sm text-slate-500">Calories cible</p><p class="text-2xl font-bold text-slate-800 dark:text-white">{target_calories} kcal</p></div>
                <div><p class="text-sm text-slate-500">Protéines</p><p class="text-2xl font-bold text-slate-800 dark:text-white">{target_proteins} g</p></div>
                <div><p class="text-sm text-slate-500">Glucides</p><p class="text-2xl font-bold text-slate-800 dark:text-white">{target_carbs} g</p></div>
                <div><p class="text-sm text-slate-500">Lipides</p><p class="text-2xl font-bold text-slate-800 dark:text-white">{target_fat} g</p></div>
            </div>
        </div>"""
    else:
        target_calories = target_proteins = target_carbs = target_fat = 0
        profile_block = """
        <div class="rounded-2xl border border-amber-200 bg-amber-50 p-6">
            <h2 class="text-xl font-bold text-amber-800">Profil incomplet</h2>
            <p class="mt-2 text-amber-700">Complétez votre profil pour calculer vos objectifs nutritionnels personnalisés.</p>
            <a href="/profile" class="mt-4 inline-block rounded-xl bg-green-700 px-5 py-3 font-semibold text-white">Compléter mon profil</a>
        </div>"""

    history = "".join(f"""
        <article class="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
            <div class="flex flex-wrap items-start justify-between gap-2">
                <div><h3 class="font-bold text-slate-800 dark:text-white">{escape(x.recipe_name)}</h3>
                <p class="text-sm text-slate-500">{round(x.consumed_percent)}% de la recette · {escape(x.consumed_at[11:16] if len(x.consumed_at) >= 16 else x.consumed_at)}</p></div>
                <span class="recipe-tag recipe-tag--fridge">🔥 {round(x.calories or 0)} kcal</span>
            </div>
            <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-600 dark:text-slate-300">
                <span>P {round(x.proteines or 0)} g</span><span>G {round(x.glucides or 0)} g</span><span>L {round(x.lipides or 0)} g</span>
            </div>
        </article>""" for x in intakes)
    if not history:
        history = "<div class='rounded-xl border border-dashed border-slate-300 p-5 text-slate-500'>Rien de mangé n'a encore été enregistré aujourd'hui. Allez dans Recettes et choisissez la portion consommée.</div>"

    leftover_html = "".join(f"""
        <div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <strong class="text-slate-800">🥡 {escape(x.recipe_name)}</strong>
            <p class="mt-1 text-sm text-slate-600">{round(x.remaining_percent)}% restant · environ {round(x.calories_remaining or 0)} kcal</p>
        </div>""" for x in leftovers)
    if not leftover_html:
        leftover_html = "<p class='text-sm text-slate-500'>Aucun reste de recette actuellement.</p>"

    added_notice = """
    <div class="rounded-xl border border-green-200 bg-green-50 px-4 py-3 font-semibold text-green-800">✅ Repas ajouté à votre suivi nutritionnel.</div>
    """ if request.query_params.get("added") == "1" else ""

    body = f"""
    <div class="space-y-6">
        <div><h1 class="text-3xl font-bold text-slate-800 dark:text-white">Nutrition</h1>
        <p class="mt-2 text-slate-600 dark:text-slate-300">Suivez ce que vous avez réellement mangé, pas simplement ce qui se trouve dans votre frigo.</p></div>
        {added_notice}
        {profile_block}
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stat_card("Calories mangées", total_calories, "kcal", progress(total_calories, target_calories), target_calories)}
            {stat_card("Protéines", total_proteins, "g", progress(total_proteins, target_proteins), target_proteins)}
            {stat_card("Glucides", total_carbs, "g", progress(total_carbs, target_carbs), target_carbs)}
            {stat_card("Lipides", total_fat, "g", progress(total_fat, target_fat), target_fat)}
        </div>
        <div class="grid gap-6 lg:grid-cols-2">
            <section class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 class="mb-4 text-2xl font-bold text-slate-800 dark:text-white">📋 Ce que j'ai mangé aujourd'hui</h2>
                <div class="space-y-3">{history}</div>
            </section>
            <section class="rounded-2xl border border-amber-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 class="mb-4 text-2xl font-bold text-slate-800 dark:text-white">🥡 Restes dans le frigo</h2>
                <div class="space-y-3">{leftover_html}</div>
                <a href="/fridge" class="mt-4 inline-flex rounded-xl bg-green-700 px-4 py-2 font-semibold text-white">Voir mon frigo</a>
            </section>
        </div>
    </div>"""
    return render_page("Nutrition", "/nutrition", body, request)
