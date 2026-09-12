from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt

from app.core.jwt import ALGORITHM, SECRET_KEY
from app.core.metabolism import compute_bmr_tdee
from app.db.database import SessionLocal
from app.db.models import UserDB
from app.web.layout import get_token_from_request, render_page, require_auth

router = APIRouter()

SEX_OPTIONS = [("male", "Homme"), ("female", "Femme")]
ACTIVITY_OPTIONS = [
    ("sedentary", "Sédentaire (peu ou pas d'exercice)"),
    ("light", "Légèrement actif (1-3 j/semaine)"),
    ("moderate", "Modérément actif (3-5 j/semaine)"),
    ("intense", "Très actif (6-7 j/semaine)"),
]
GOAL_OPTIONS = [
    ("loss", "Perte de poids"),
    ("maintain", "Maintien"),
    ("gain", "Prise de poids"),
]


def get_user_id_from_cookie(request: Request):
    token = get_token_from_request(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def _options_html(options, selected):
    return "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{label}</option>'
        for value, label in options
    )


def _nutrition_block(user: UserDB | None) -> str:
    has_full_profile = bool(
        user and all([user.age, user.weight, user.height, user.sex, user.activity, user.goal])
    )
    if not has_full_profile:
        return """
            <p class="text-slate-600">
                Complète et enregistre le formulaire ci-dessus pour voir apparaître ici ton
                métabolisme de base, tes calories de maintien, ton objectif calorique et tes macros.
            </p>
        """

    result = compute_bmr_tdee(user)
    macros = result["macros"]
    return f"""
        <div class="grid gap-4 md:grid-cols-3">
            <div class="rounded-xl border border-green-100 bg-green-50 p-4">
                <h3 class="text-lg font-semibold text-slate-800">Métabolisme de base</h3>
                <p class="mt-2 text-slate-600">{result['bmr']} kcal/jour</p>
            </div>
            <div class="rounded-xl border border-green-100 bg-green-50 p-4">
                <h3 class="text-lg font-semibold text-slate-800">Calories de maintien</h3>
                <p class="mt-2 text-slate-600">{result['tdee']} kcal/jour</p>
            </div>
            <div class="rounded-xl border border-green-100 bg-green-50 p-4">
                <h3 class="text-lg font-semibold text-slate-800">Objectif calorique</h3>
                <p class="mt-2 text-slate-600">{result['target_calories']} kcal/jour</p>
            </div>
        </div>
        <div class="mt-4 grid gap-4 md:grid-cols-3">
            <div class="rounded-xl border border-slate-200 bg-white p-4">
                <h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Protéines</h3>
                <p class="mt-1 text-xl font-bold text-slate-800">{macros['proteins_g']} g</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
                <h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Lipides</h3>
                <p class="mt-1 text-xl font-bold text-slate-800">{macros['fats_g']} g</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
                <h3 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Glucides</h3>
                <p class="mt-1 text-xl font-bold text-slate-800">{macros['carbs_g']} g</p>
            </div>
        </div>
    """


def _render_profile_body(user: UserDB | None, message: str = "") -> str:
    age = user.age if user and user.age is not None else ""
    weight = user.weight if user and user.weight is not None else ""
    height = user.height if user and user.height is not None else ""
    sex = user.sex if user else ""
    activity = user.activity if user else ""
    goal = user.goal if user else ""

    feedback = (
        f'<p class="mb-4 rounded-xl bg-green-100 px-4 py-3 font-semibold text-green-700">{message}</p>'
        if message
        else ""
    )

    return f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Profil</h1>
            {feedback}
            <form method="post" action="/profile" class="grid gap-4 md:grid-cols-2">
                <div class="flex flex-col gap-2">
                    <label for="age" class="font-semibold text-slate-700">Âge</label>
                    <input id="age" name="age" type="number" min="1" max="120" value="{age}" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="sex" class="font-semibold text-slate-700">Sexe</label>
                    <select id="sex" name="sex" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500">
                        <option value="" disabled {"selected" if not sex else ""}>Choisir...</option>
                        {_options_html(SEX_OPTIONS, sex)}
                    </select>
                </div>
                <div class="flex flex-col gap-2">
                    <label for="weight" class="font-semibold text-slate-700">Poids (kg)</label>
                    <input id="weight" name="weight" type="number" step="0.1" min="1" value="{weight}" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="height" class="font-semibold text-slate-700">Taille (cm)</label>
                    <input id="height" name="height" type="number" step="0.1" min="1" value="{height}" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="activity" class="font-semibold text-slate-700">Niveau d'activité</label>
                    <select id="activity" name="activity" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500">
                        <option value="" disabled {"selected" if not activity else ""}>Choisir...</option>
                        {_options_html(ACTIVITY_OPTIONS, activity)}
                    </select>
                </div>
                <div class="flex flex-col gap-2">
                    <label for="goal" class="font-semibold text-slate-700">Objectif</label>
                    <select id="goal" name="goal" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500">
                        <option value="" disabled {"selected" if not goal else ""}>Choisir...</option>
                        {_options_html(GOAL_OPTIONS, goal)}
                    </select>
                </div>
                <div class="md:col-span-2">
                    <button type="submit"
                        class="inline-flex rounded-xl bg-green-700 px-5 py-3 font-semibold text-white transition hover:bg-green-800">
                        Enregistrer
                    </button>
                </div>
            </form>
        </div>
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h2 class="mb-4 text-2xl font-bold text-slate-800">Calcul nutritionnel</h2>
            {_nutrition_block(user)}
        </div>
    """


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id_from_cookie(request)
    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first() if user_id else None
        body = _render_profile_body(user)

    return render_page("Profil", "/profile", body, request)


@router.post("/profile", response_class=HTMLResponse)
def update_profile(
    request: Request,
    age: int = Form(...),
    sex: str = Form(...),
    weight: float = Form(...),
    height: float = Form(...),
    activity: str = Form(...),
    goal: str = Form(...),
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id_from_cookie(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    with SessionLocal() as db:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            return RedirectResponse(url="/login", status_code=302)

        user.age = age
        user.sex = sex
        user.weight = weight
        user.height = height
        user.activity = activity
        user.goal = goal
        db.add(user)
        db.commit()
        db.refresh(user)

        body = _render_profile_body(user, message="Profil enregistré avec succès.")

    return render_page("Profil", "/profile", body, request)