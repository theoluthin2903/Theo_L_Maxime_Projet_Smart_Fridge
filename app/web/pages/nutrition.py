from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.metabolism import compute_bmr_tdee
from app.db.database import SessionLocal
from app.db.models import UserDB
from app.web.data import get_usda_foods, load_fridge_items
from app.web.layout import require_auth, render_page

router = APIRouter()


def get_user_id_from_cookie(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        return None

    try:
        from jose import jwt
        from app.core.jwt import SECRET_KEY, ALGORITHM

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        return payload.get("sub")

    except Exception:
        return None


@router.get("/nutrition", response_class=HTMLResponse)
def nutrition_page(request: Request):

    redirect = require_auth(request)

    if redirect:
        return redirect

    user_id = get_user_id_from_cookie(request)

    # Récupération du profil
    user = None

    if user_id:
        with SessionLocal() as db:
            user = (
                db.query(UserDB)
                .filter(UserDB.id == int(user_id))
                .first()
            )

    # Calcul des objectifs
    nutrition = None

    if user:
        if all([
            user.age is not None,
            user.weight is not None,
            user.height is not None,
            user.sex,
            user.activity,
            user.goal,
        ]):
            nutrition = compute_bmr_tdee(user)

    # Récupération du frigo de l'utilisateur
    items = load_fridge_items(user_id)

    total_calories = 0
    total_proteins = 0
    total_carbs = 0
    total_fat = 0

    products_html = ""

    for item in items:

        name = item.get("name", "")
        quantity = int(item.get("quantity") or 1)

        foods = get_usda_foods(name, limit=1)

        if not foods:
            products_html += f"""
            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div class="flex justify-between">
                    <div>
                        <h3 class="font-semibold text-slate-800">
                            {name}
                        </h3>
                        <p class="text-sm text-slate-500">
                            Quantité : {quantity}
                        </p>
                    </div>

                    <span class="text-sm text-slate-500">
                        Données nutritionnelles indisponibles
                    </span>
                </div>
            </div>
            """

            continue

        food = foods[0]

        calories = float(food.get("calories", 0) or 0) * quantity
        proteins = float(food.get("proteines", 0) or 0) * quantity
        carbs = float(food.get("glucides", 0) or 0) * quantity
        fat = float(food.get("lipides", 0) or 0) * quantity

        total_calories += calories
        total_proteins += proteins
        total_carbs += carbs
        total_fat += fat

        products_html += f"""
        <div class="rounded-xl border border-green-100 bg-green-50 p-4">

            <div class="flex items-center justify-between gap-4">

                <div>
                    <h3 class="font-semibold text-slate-800">
                        {name}
                    </h3>

                    <p class="text-sm text-slate-500">
                        Quantité : {quantity}
                    </p>
                </div>

                <div class="text-right">
                    <p class="font-bold text-slate-800">
                        {round(calories)} kcal
                    </p>

                    <p class="text-sm text-slate-500">
                        P : {round(proteins)} g
                        · G : {round(carbs)} g
                        · L : {round(fat)} g
                    </p>
                </div>

            </div>

        </div>
        """

    total_calories = round(total_calories)
    total_proteins = round(total_proteins)
    total_carbs = round(total_carbs)
    total_fat = round(total_fat)

    # Objectifs du profil
    if nutrition:

        target_calories = nutrition["target_calories"]
        target_proteins = nutrition["macros"]["proteins_g"]
        target_carbs = nutrition["macros"]["carbs_g"]
        target_fat = nutrition["macros"]["fats_g"]

        calorie_percent = min(
            round((total_calories / target_calories) * 100),
            100,
        ) if target_calories else 0

        protein_percent = min(
            round((total_proteins / target_proteins) * 100),
            100,
        ) if target_proteins else 0

        carbs_percent = min(
            round((total_carbs / target_carbs) * 100),
            100,
        ) if target_carbs else 0

        fat_percent = min(
            round((total_fat / target_fat) * 100),
            100,
        ) if target_fat else 0

        profile_block = f"""
        <div class="rounded-2xl border border-green-100 bg-green-50 p-6">

            <h2 class="text-xl font-bold text-slate-800">
                Tes objectifs quotidiens
            </h2>

            <div class="mt-4 grid gap-4 md:grid-cols-4">

                <div>
                    <p class="text-sm text-slate-500">Calories</p>
                    <p class="text-2xl font-bold">
                        {target_calories} kcal
                    </p>
                </div>

                <div>
                    <p class="text-sm text-slate-500">Protéines</p>
                    <p class="text-2xl font-bold">
                        {target_proteins} g
                    </p>
                </div>

                <div>
                    <p class="text-sm text-slate-500">Glucides</p>
                    <p class="text-2xl font-bold">
                        {target_carbs} g
                    </p>
                </div>

                <div>
                    <p class="text-sm text-slate-500">Lipides</p>
                    <p class="text-2xl font-bold">
                        {target_fat} g
                    </p>
                </div>

            </div>

        </div>
        """

    else:

        calorie_percent = 0
        protein_percent = 0
        carbs_percent = 0
        fat_percent = 0

        profile_block = """
        <div class="rounded-2xl border border-amber-200 bg-amber-50 p-6">

            <h2 class="text-xl font-bold text-amber-800">
                Profil incomplet
            </h2>

            <p class="mt-2 text-amber-700">
                Complète ton profil pour obtenir tes objectifs
                nutritionnels personnalisés.
            </p>

            <a
                href="/profile"
                class="mt-4 inline-block rounded-xl bg-green-700 px-5 py-3 font-semibold text-white"
            >
                Compléter mon profil
            </a>

        </div>
        """

    if not products_html:

        products_html = """
        <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">

            <h3 class="font-semibold text-slate-700">
                Ton frigo est vide
            </h3>

            <p class="mt-2 text-sm text-slate-500">
                Ajoute des aliments dans ton frigo pour voir
                leurs informations nutritionnelles.
            </p>

            <a
                href="/fridge"
                class="mt-4 inline-block rounded-xl bg-green-700 px-5 py-3 font-semibold text-white"
            >
                Aller au frigo
            </a>

        </div>
        """

    body = f"""
    <div class="space-y-6">

        <div>
            <h1 class="text-3xl font-bold text-slate-800">
                Nutrition
            </h1>

            <p class="mt-2 text-slate-600">
                Suis les apports nutritionnels des aliments présents dans ton frigo.
            </p>
        </div>

        {profile_block}

        <div class="grid gap-4 md:grid-cols-4">

            <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm">

                <p class="text-sm text-slate-500">
                    Calories
                </p>

                <p class="mt-2 text-3xl font-bold text-slate-800">
                    {total_calories}
                    <span class="text-base font-normal">kcal</span>
                </p>

                <div class="mt-4 h-3 rounded-full bg-slate-200">
                    <div
                        class="h-3 rounded-full bg-green-600"
                        style="width: {calorie_percent}%"
                    ></div>
                </div>

                <p class="mt-2 text-sm text-slate-500">
                    {calorie_percent}% de l'objectif
                </p>

            </div>


            <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm">

                <p class="text-sm text-slate-500">
                    Protéines
                </p>

                <p class="mt-2 text-3xl font-bold text-slate-800">
                    {total_proteins}
                    <span class="text-base font-normal">g</span>
                </p>

                <div class="mt-4 h-3 rounded-full bg-slate-200">
                    <div
                        class="h-3 rounded-full bg-green-600"
                        style="width: {protein_percent}%"
                    ></div>
                </div>

                <p class="mt-2 text-sm text-slate-500">
                    {protein_percent}% de l'objectif
                </p>

            </div>


            <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm">

                <p class="text-sm text-slate-500">
                    Glucides
                </p>

                <p class="mt-2 text-3xl font-bold text-slate-800">
                    {total_carbs}
                    <span class="text-base font-normal">g</span>
                </p>

                <div class="mt-4 h-3 rounded-full bg-slate-200">
                    <div
                        class="h-3 rounded-full bg-green-600"
                        style="width: {carbs_percent}%"
                    ></div>
                </div>

                <p class="mt-2 text-sm text-slate-500">
                    {carbs_percent}% de l'objectif
                </p>

            </div>


            <div class="rounded-2xl border border-green-100 bg-white p-5 shadow-sm">

                <p class="text-sm text-slate-500">
                    Lipides
                </p>

                <p class="mt-2 text-3xl font-bold text-slate-800">
                    {total_fat}
                    <span class="text-base font-normal">g</span>
                </p>

                <div class="mt-4 h-3 rounded-full bg-slate-200">
                    <div
                        class="h-3 rounded-full bg-green-600"
                        style="width: {fat_percent}%"
                    ></div>
                </div>

                <p class="mt-2 text-sm text-slate-500">
                    {fat_percent}% de l'objectif
                </p>

            </div>

        </div>


        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">

            <h2 class="mb-5 text-2xl font-bold text-slate-800">
                Aliments du frigo
            </h2>

            <div class="space-y-3">
                {products_html}
            </div>

        </div>

    </div>
    """

    return render_page(
        "Nutrition",
        "/nutrition",
        body,
        request,
    )