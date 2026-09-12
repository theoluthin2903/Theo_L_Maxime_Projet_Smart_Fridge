from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt

from app.core.jwt import ALGORITHM, SECRET_KEY
from app.core.metabolism import compute_bmr_tdee
from app.db.database import SessionLocal
from app.db.models import UserDB
from app.web.data import get_food_nutrition, load_fridge_items
from app.web.layout import get_token_from_request, require_auth, render_page

router = APIRouter()


def get_user_id(request: Request):
    token = get_token_from_request(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def progress(value, target):
    if not target or target <= 0:
        return 0
    return min(round((value / target) * 100), 100)


def stat_card(title, value, unit, percent):
    return f"""
    <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm">
        <p class="text-sm text-slate-500">{title}</p>
        <p class="mt-2 text-3xl font-bold text-slate-800">{value} <span class="text-base font-normal">{unit}</span></p>
        <div class="mt-4 h-3 rounded-full bg-slate-200">
            <div class="h-3 rounded-full bg-green-600" style="width: {percent}%"></div>
        </div>
        <p class="mt-2 text-sm text-slate-500">{percent}% de l'objectif</p>
    </div>
    """


@router.get("/nutrition", response_class=HTMLResponse)
def nutrition_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None

    nutrition = None
    if user and all([
        user.age is not None,
        user.weight is not None,
        user.height is not None,
        user.sex,
        user.activity,
        user.goal,
    ]):
        nutrition = compute_bmr_tdee(user)

    items = load_fridge_items(int(user_id)) if user_id else []

    total_calories = 0.0
    total_proteins = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    cards = []

    for item in items:
        name = (item.get("name") or "").strip()
        quantity = int(item.get("quantity") or 1)
        if not name:
            continue

        food = get_food_nutrition(name)

        calories = float(food.get("calories", 0) or 0) * quantity
        proteins = float(food.get("proteines", 0) or 0) * quantity
        carbs = float(food.get("glucides", 0) or 0) * quantity
        fat = float(food.get("lipides", 0) or 0) * quantity

        total_calories += calories
        total_proteins += proteins
        total_carbs += carbs
        total_fat += fat

        estimated_label = ""
        if food.get("estimated"):
            estimated_label = '<span class="text-xs text-amber-600">Valeurs estimées</span>'

        cards.append(f"""
        <div class="rounded-xl border border-green-100 bg-green-50 p-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <h3 class="font-semibold text-slate-800">{name}</h3>
                    <p class="text-sm text-slate-500">Quantité : {quantity}</p>
                    {estimated_label}
                </div>
                <div class="text-right">
                    <p class="font-bold text-slate-800">{round(calories)} kcal</p>
                    <p class="text-sm text-slate-500">P : {round(proteins)} g · G : {round(carbs)} g · L : {round(fat)} g</p>
                </div>
            </div>
        </div>
        """)

    total_calories = round(total_calories)
    total_proteins = round(total_proteins)
    total_carbs = round(total_carbs)
    total_fat = round(total_fat)

    if nutrition:
        target_calories = nutrition["target_calories"]
        target_proteins = nutrition["macros"]["proteins_g"]
        target_carbs = nutrition["macros"]["carbs_g"]
        target_fat = nutrition["macros"]["fats_g"]

        profile_block = f"""
        <div class="rounded-2xl border border-green-100 bg-green-50 p-6">
            <h2 class="text-xl font-bold text-slate-800">Tes objectifs quotidiens</h2>
            <div class="mt-4 grid gap-4 md:grid-cols-4">
                <div><p class="text-sm text-slate-500">Calories</p><p class="text-2xl font-bold text-slate-800">{target_calories} kcal</p></div>
                <div><p class="text-sm text-slate-500">Protéines</p><p class="text-2xl font-bold text-slate-800">{target_proteins} g</p></div>
                <div><p class="text-sm text-slate-500">Glucides</p><p class="text-2xl font-bold text-slate-800">{target_carbs} g</p></div>
                <div><p class="text-sm text-slate-500">Lipides</p><p class="text-2xl font-bold text-slate-800">{target_fat} g</p></div>
            </div>
        </div>
        """
    else:
        target_calories = target_proteins = target_carbs = target_fat = 0
        profile_block = """
        <div class="rounded-2xl border border-amber-200 bg-amber-50 p-6">
            <h2 class="text-xl font-bold text-amber-800">Profil incomplet</h2>
            <p class="mt-2 text-amber-700">Complète ton profil pour obtenir tes objectifs nutritionnels personnalisés.</p>
            <a href="/profile" class="mt-4 inline-block rounded-xl bg-green-700 px-5 py-3 font-semibold text-white">Compléter mon profil</a>
        </div>
        """

    cards_html = "".join(cards) or """
    <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
        <h3 class="font-semibold text-slate-700">Ton frigo est vide</h3>
        <p class="mt-2 text-sm text-slate-500">Ajoute des aliments dans ton frigo pour voir leurs informations nutritionnelles.</p>
        <a href="/fridge" class="mt-4 inline-block rounded-xl bg-green-700 px-5 py-3 font-semibold text-white">Aller au frigo</a>
    </div>
    """

    body = f"""
    <div class="space-y-6">
        <div>
            <h1 class="text-3xl font-bold text-slate-800">Nutrition</h1>
            <p class="mt-2 text-slate-600">Suis les apports nutritionnels des aliments présents dans ton frigo.</p>
        </div>

        {profile_block}

        <div class="grid gap-4 md:grid-cols-4">
            {stat_card("Calories", total_calories, "kcal", progress(total_calories, target_calories))}
            {stat_card("Protéines", total_proteins, "g", progress(total_proteins, target_proteins))}
            {stat_card("Glucides", total_carbs, "g", progress(total_carbs, target_carbs))}
            {stat_card("Lipides", total_fat, "g", progress(total_fat, target_fat))}
        </div>

        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h2 class="mb-5 text-2xl font-bold text-slate-800">Aliments du frigo</h2>
            <div class="space-y-3">{cards_html}</div>
        </div>
    </div>
    """

    return render_page("Nutrition", "/nutrition", body, request)
