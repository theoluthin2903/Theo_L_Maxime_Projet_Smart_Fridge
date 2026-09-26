from datetime import date, datetime, timedelta
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.metabolism import compute_bmr_tdee
from app.db.database import SessionLocal
from app.db.models import (MealPlanConsumptionDB, MealPlanDB, NutritionIntakeDB, RecipeLeftoverDB, RecipeNutritionCacheDB, UserDB)
from app.web.data import get_current_app_date, get_fridge_search_query, get_recipe_instructions_fr, get_themealdb_recipes, load_fridge_items
from app.web.layout import render_page
from app.web.nutrition_engine import compute_nutrition_for_recipes_async
from app.web.pages.fridge import get_user_id_from_cookie

router = APIRouter()
MEALS = [("breakfast", "🌅 Petit-déjeuner"), ("lunch", "☀️ Déjeuner"), ("dinner", "🌙 Dîner")]
WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _parse_start(value: str | None, fallback: date) -> date:
    try:
        chosen = date.fromisoformat(value) if value else fallback
    except ValueError:
        chosen = fallback
    return chosen - timedelta(days=chosen.weekday())


def _status(percent: float) -> tuple[str, str]:
    if percent >= 100:
        return "danger", "🔴 Objectif dépassé"
    if percent >= 80:
        return "warning", "🟠 Proche de l’objectif"
    return "good", "🟢 Dans l’objectif"


@router.get("/planner", response_class=HTMLResponse)
async def planner_page(request: Request, start: str | None = None):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)

    uid = int(user_id)
    today = get_current_app_date(uid)
    week_start = _parse_start(start, today)
    days = [week_start + timedelta(days=i) for i in range(7)]
    week_end = days[-1]

    with SessionLocal() as db:
        rows = db.query(MealPlanDB).filter(
            MealPlanDB.user_id == uid,
            MealPlanDB.plan_date >= week_start.isoformat(),
            MealPlanDB.plan_date <= week_end.isoformat(),
        ).all()
        consumption_rows = db.query(MealPlanConsumptionDB).filter(
            MealPlanConsumptionDB.user_id == uid,
            MealPlanConsumptionDB.meal_plan_id.in_([r.id for r in rows]),
        ).all() if rows else []
        profile = db.query(UserDB).filter(UserDB.id == uid).first()
        targets = None
        if profile and all(getattr(profile, field, None) is not None for field in ("age", "weight", "height", "sex", "activity", "goal")):
            targets = compute_bmr_tdee(profile)
    planned = {(r.plan_date, r.meal_type): r for r in rows}
    consumed_by_plan = {r.meal_plan_id: r for r in consumption_rows}

    load_fridge_items(uid)
    ingredient = get_fridge_search_query()
    suggestions = get_themealdb_recipes(ingredient, limit=12) if ingredient else []

    # Calcule une seule fois la nutrition des recettes proposées puis la garde en base.
    # Le planning peut ainsi réutiliser les valeurs les semaines suivantes sans refaire les appels USDA.
    if suggestions:
        try:
            nutrition_results = await compute_nutrition_for_recipes_async([r.get("raw_meal") or {} for r in suggestions])
        except Exception as exc:
            print(f"[Planning] Nutrition indisponible : {exc}")
            nutrition_results = [None] * len(suggestions)
        now = datetime.now().isoformat(timespec="seconds")
        with SessionLocal() as db:
            for recipe, nutrition in zip(suggestions, nutrition_results):
                if not nutrition or not recipe.get("meal_id"):
                    continue
                mid = str(recipe["meal_id"])
                cached = db.query(RecipeNutritionCacheDB).filter(RecipeNutritionCacheDB.meal_id == mid).first()
                values = {
                    "recipe_name": recipe.get("name") or "Recette",
                    "calories": float(nutrition.get("calories", 0) or 0),
                    "proteines": float(nutrition.get("proteines", 0) or 0),
                    "glucides": float(nutrition.get("glucides", 0) or 0),
                    "lipides": float(nutrition.get("lipides", 0) or 0),
                    "estimated": 1 if nutrition.get("estimated") else 0,
                    "updated_at": now,
                }
                if cached:
                    for key, value in values.items():
                        setattr(cached, key, value)
                else:
                    db.add(RecipeNutritionCacheDB(meal_id=mid, **values))
            db.commit()

    meal_ids = {str(r.meal_id) for r in rows if r.meal_id}
    meal_ids.update(str(r.get("meal_id")) for r in suggestions if r.get("meal_id"))
    nutrition_by_id = {}
    if meal_ids:
        with SessionLocal() as db:
            cached_rows = db.query(RecipeNutritionCacheDB).filter(RecipeNutritionCacheDB.meal_id.in_(meal_ids)).all()
            nutrition_by_id = {r.meal_id: r for r in cached_rows}

    options = "".join(
        f'<option value="{escape(str(r.get("meal_id") or ""), quote=True)}|{escape(r.get("name") or "", quote=True)}">{escape(r.get("name") or "Recette")}</option>'
        for r in suggestions
    )

    target_cal = float(targets["target_calories"]) if targets else 0
    target_p = float(targets["macros"]["proteins_g"]) if targets else 0
    target_g = float(targets["macros"]["carbs_g"]) if targets else 0
    target_l = float(targets["macros"]["fats_g"]) if targets else 0

    day_cards = ""
    week_totals = {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}
    warning_days = 0
    danger_days = 0

    for day in days:
        slots = ""
        totals = {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}
        for meal_type, meal_label in MEALS:
            row = planned.get((day.isoformat(), meal_type))
            current = escape(row.recipe_name) if row else "Aucun repas prévu"
            n = nutrition_by_id.get(str(row.meal_id)) if row and row.meal_id else None
            nutrition_html = ""
            if n:
                totals["calories"] += float(n.calories or 0)
                totals["proteines"] += float(n.proteines or 0)
                totals["glucides"] += float(n.glucides or 0)
                totals["lipides"] += float(n.lipides or 0)
                nutrition_html = f'''<div class="meal-plan-slot-nutrition">
                    <span>🔥 {round(n.calories or 0)} kcal</span><span>P {round(n.proteines or 0)} g</span>
                    <span>G {round(n.glucides or 0)} g</span><span>L {round(n.lipides or 0)} g</span>
                </div>'''
            remove = f'''<form method="post" action="/planner/delete" class="inline">
                <input type="hidden" name="plan_date" value="{day.isoformat()}"><input type="hidden" name="meal_type" value="{meal_type}">
                <button class="meal-plan-remove" title="Retirer ce repas">✕</button></form>''' if row else ""
            consumption = consumed_by_plan.get(row.id) if row else None
            if row and consumption:
                action_html = f'''<div class="meal-plan-consumed">✅ Mangé à {round(consumption.consumed_percent)} %</div>'''
            elif row and n:
                action_html = f'''<a class="meal-plan-prepare" href="/planner/prepare/{row.id}">👨‍🍳 Préparer</a>'''
            elif row:
                action_html = '<div class="meal-plan-no-nutrition">Nutrition indisponible pour préparer ce repas.</div>'
            else:
                action_html = ""
            slots += f'''
            <div class="meal-plan-slot {'meal-plan-slot--filled' if row else ''}">
                <div class="meal-plan-slot__head"><strong>{meal_label}</strong>{remove}</div>
                <p class="meal-plan-current">{current}</p>{nutrition_html}{action_html}
                <form method="post" action="/planner/save" class="meal-plan-form">
                    <input type="hidden" name="plan_date" value="{day.isoformat()}"><input type="hidden" name="meal_type" value="{meal_type}">
                    <select name="recipe_value" required><option value="">Choisir une recette…</option>{options}</select>
                    <button type="submit">{'Modifier' if row else 'Planifier'}</button>
                </form>
            </div>'''

        for key in week_totals:
            week_totals[key] += totals[key]
        pct = (totals["calories"] / target_cal * 100) if target_cal else 0
        state, state_label = _status(pct)
        if state == "danger": danger_days += 1
        elif state == "warning": warning_days += 1
        marker = '<span class="meal-plan-today">Aujourd’hui</span>' if day == today else ""
        summary = ""
        if targets:
            summary = f'''<div class="meal-plan-day-summary meal-plan-day-summary--{state}">
                <div class="meal-plan-day-summary__top"><strong>Prévision du jour</strong><span>{round(pct)}%</span></div>
                <div class="meal-plan-day-summary__bar"><i style="width:{min(pct,100):.1f}%"></i></div>
                <strong class="meal-plan-day-summary__cal">🔥 {round(totals['calories'])} / {round(target_cal)} kcal</strong>
                <div class="meal-plan-day-summary__macros"><span>P {round(totals['proteines'])}/{round(target_p)} g</span><span>G {round(totals['glucides'])}/{round(target_g)} g</span><span>L {round(totals['lipides'])}/{round(target_l)} g</span></div>
                <small>{state_label}</small>
            </div>'''
        day_cards += f'''<article class="meal-plan-day meal-plan-day--{state}">
            <header><div><span class="meal-plan-weekday">{WEEKDAYS[day.weekday()]}</span><span class="meal-plan-date">{day.strftime('%d/%m')}</span></div>{marker}</header>
            {summary}<div class="meal-plan-slots">{slots}</div>
        </article>'''

    prev_start = (week_start - timedelta(days=7)).isoformat()
    next_start = (week_start + timedelta(days=7)).isoformat()
    weekly_summary = ""
    if targets:
        avg = {k: v / 7 for k, v in week_totals.items()}
        weekly_summary = f'''<div class="meal-plan-week-summary">
          <div><span>Moyenne prévue / jour</span><strong>🔥 {round(avg['calories'])} kcal</strong></div>
          <div><span>Protéines</span><strong>{round(avg['proteines'])} g</strong></div>
          <div><span>Glucides</span><strong>{round(avg['glucides'])} g</strong></div>
          <div><span>Lipides</span><strong>{round(avg['lipides'])} g</strong></div>
          <div><span>État de la semaine</span><strong>{'🔴 ' + str(danger_days) + ' jour(s) dépassé(s)' if danger_days else ('🟠 ' + str(warning_days) + ' jour(s) proche(s)' if warning_days else '🟢 Planning équilibré')}</strong></div>
        </div>'''

    body = f'''
    <section class="space-y-6">
      <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div><span class="recipe-tag recipe-tag--fridge">🍽️ Organisation</span><h1 class="mt-3 text-3xl font-extrabold">Planificateur de repas</h1>
          <p class="mt-2 text-slate-500 dark:text-slate-300">Planifiez la semaine et voyez vos calories/macros prévues avant même de manger.</p></div>
          <div class="meal-plan-nav"><a href="/planner?start={prev_start}">← Semaine précédente</a><a href="/planner">Aujourd’hui</a><a href="/planner?start={next_start}">Semaine suivante →</a></div>
        </div>
        <div class="mt-5 flex flex-wrap gap-2"><span class="recipe-tag">📅 {week_start.strftime('%d/%m')} → {week_end.strftime('%d/%m/%Y')}</span><span class="recipe-tag recipe-tag--fridge">🍳 {len(suggestions)} recettes proposées depuis le frigo</span></div>
      </div>
      {weekly_summary}
      {'<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">Complétez votre profil (âge, taille, poids, sexe, activité et objectif) pour activer les prévisions nutritionnelles.</div>' if not targets else ''}
      {'<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">Ajoutez des produits au frigo pour obtenir des recettes à planifier.</div>' if not suggestions else ''}
      <div class="meal-plan-grid">{day_cards}</div>
    </section>'''
    return render_page("Planificateur", "/planner", body, request)


@router.post("/planner/save")
def save_meal(request: Request, plan_date: str = Form(...), meal_type: str = Form(...), recipe_value: str = Form(...)):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)
    if meal_type not in {x[0] for x in MEALS}:
        return RedirectResponse("/planner", status_code=303)
    try:
        date.fromisoformat(plan_date)
    except ValueError:
        return RedirectResponse("/planner", status_code=303)
    meal_id, sep, recipe_name = recipe_value.partition("|")
    if not sep or not recipe_name.strip():
        return RedirectResponse(f"/planner?start={quote(plan_date)}", status_code=303)
    with SessionLocal() as db:
        row = db.query(MealPlanDB).filter(MealPlanDB.user_id == int(user_id), MealPlanDB.plan_date == plan_date, MealPlanDB.meal_type == meal_type).first()
        if row:
            row.meal_id, row.recipe_name = meal_id or None, recipe_name.strip()
        else:
            db.add(MealPlanDB(user_id=int(user_id), plan_date=plan_date, meal_type=meal_type, meal_id=meal_id or None, recipe_name=recipe_name.strip()))
        db.commit()
    return RedirectResponse(f"/planner?start={quote(plan_date)}", status_code=303)


@router.post("/planner/delete")
def delete_meal(request: Request, plan_date: str = Form(...), meal_type: str = Form(...)):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)
    with SessionLocal() as db:
        db.query(MealPlanDB).filter(MealPlanDB.user_id == int(user_id), MealPlanDB.plan_date == plan_date, MealPlanDB.meal_type == meal_type).delete()
        db.commit()
    return RedirectResponse(f"/planner?start={quote(plan_date)}", status_code=303)

@router.get("/planner/prepare/{plan_id}", response_class=HTMLResponse)
def prepare_planned_meal(plan_id: int, request: Request):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)
    uid = int(user_id)
    with SessionLocal() as db:
        plan = db.query(MealPlanDB).filter(MealPlanDB.id == plan_id, MealPlanDB.user_id == uid).first()
        if not plan:
            return RedirectResponse("/planner", status_code=303)
        consumed = db.query(MealPlanConsumptionDB).filter(MealPlanConsumptionDB.user_id == uid, MealPlanConsumptionDB.meal_plan_id == plan.id).first()
        nutrition = db.query(RecipeNutritionCacheDB).filter(RecipeNutritionCacheDB.meal_id == str(plan.meal_id)).first() if plan.meal_id else None
    instructions = get_recipe_instructions_fr(str(plan.meal_id)) if plan.meal_id else "Préparation non disponible."
    meal_label = dict(MEALS).get(plan.meal_type, plan.meal_type)
    nutrition_html = ""
    if nutrition:
        nutrition_html = f'''<div class="planner-prepare-macros">
          <div><span>🔥 Calories</span><strong>{round(nutrition.calories or 0)} kcal</strong></div><div><span>🥩 Protéines</span><strong>{round(nutrition.proteines or 0)} g</strong></div>
          <div><span>🍚 Glucides</span><strong>{round(nutrition.glucides or 0)} g</strong></div><div><span>🥑 Lipides</span><strong>{round(nutrition.lipides or 0)} g</strong></div></div>'''
    if consumed:
        consume_box = f'<div class="planner-prepare-done">✅ Ce repas a déjà été enregistré comme mangé à {round(consumed.consumed_percent)} %.</div>'
    elif nutrition:
        consume_box = f'''<form method="post" action="/planner/consume" class="planner-prepare-consume"><input type="hidden" name="plan_id" value="{plan.id}">
          <label for="consumed_percent"><strong>🍽️ Combien avez-vous mangé ?</strong></label><select id="consumed_percent" name="consumed_percent" required>
          <option value="25">1/4 de la recette (25 %)</option><option value="50">La moitié (50 %)</option><option value="75">3/4 de la recette (75 %)</option><option value="100" selected>Toute la recette (100 %)</option></select>
          <button type="submit">✅ J’ai mangé ce repas</button><p>La portion sera ajoutée à Nutrition. La partie non mangée sera automatiquement enregistrée comme reste.</p></form>'''
    else:
        consume_box = '<div class="planner-prepare-done">Nutrition indisponible : impossible d’enregistrer la portion pour ce repas.</div>'
    instructions_html = escape(instructions).replace("\n", "<br>")
    body = f'''<section class="planner-prepare-page"><a class="planner-prepare-back" href="/planner?start={quote(plan.plan_date)}">← Retour au planning</a>
      <div class="planner-prepare-hero"><div><span class="planner-prepare-kicker">{escape(meal_label)} • {escape(plan.plan_date)}</span><h1>👨‍🍳 {escape(plan.recipe_name)}</h1><p>Préparez la recette puis indiquez la quantité réellement mangée.</p></div></div>
      {nutrition_html}<article class="planner-prepare-instructions"><h2>🥣 Préparation</h2><div>{instructions_html}</div></article>{consume_box}</section>'''
    return render_page("Préparer le repas", "/planner", body, request)


@router.post("/planner/consume")
def consume_planned_meal(request: Request, plan_id: int = Form(...), consumed_percent: float = Form(...)):
    user_id = get_user_id_from_cookie(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=302)
    uid = int(user_id); percent = max(0.0, min(float(consumed_percent), 100.0)); factor = percent / 100.0; remaining = 100.0 - percent
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with SessionLocal() as db:
        plan = db.query(MealPlanDB).filter(MealPlanDB.id == plan_id, MealPlanDB.user_id == uid).first()
        if not plan: return RedirectResponse("/planner", status_code=303)
        already = db.query(MealPlanConsumptionDB).filter(MealPlanConsumptionDB.user_id == uid, MealPlanConsumptionDB.meal_plan_id == plan.id).first()
        if already: return RedirectResponse(f"/planner?start={quote(plan.plan_date)}", status_code=303)
        nutrition = db.query(RecipeNutritionCacheDB).filter(RecipeNutritionCacheDB.meal_id == str(plan.meal_id)).first() if plan.meal_id else None
        if not nutrition: return RedirectResponse(f"/planner/prepare/{plan.id}", status_code=303)
        db.add(NutritionIntakeDB(user_id=uid, meal_id=str(plan.meal_id), recipe_name=plan.recipe_name, consumed_percent=percent,
            calories=float(nutrition.calories or 0)*factor, proteines=float(nutrition.proteines or 0)*factor, glucides=float(nutrition.glucides or 0)*factor, lipides=float(nutrition.lipides or 0)*factor, consumed_at=now))
        leftover = db.query(RecipeLeftoverDB).filter(RecipeLeftoverDB.user_id == uid, RecipeLeftoverDB.meal_id == str(plan.meal_id)).first()
        if remaining > 0:
            values=dict(recipe_name=plan.recipe_name, remaining_percent=remaining, calories_remaining=float(nutrition.calories or 0)*remaining/100.0,
                proteines_remaining=float(nutrition.proteines or 0)*remaining/100.0, glucides_remaining=float(nutrition.glucides or 0)*remaining/100.0, lipides_remaining=float(nutrition.lipides or 0)*remaining/100.0, updated_at=now)
            if leftover:
                for key,value in values.items(): setattr(leftover,key,value)
            else: db.add(RecipeLeftoverDB(user_id=uid, meal_id=str(plan.meal_id), created_at=now, **values))
        elif leftover: db.delete(leftover)
        db.add(MealPlanConsumptionDB(user_id=uid, meal_plan_id=plan.id, consumed_percent=percent, consumed_at=now)); db.commit(); plan_date=plan.plan_date
    return RedirectResponse(f"/planner?start={quote(plan_date)}&consumed=1", status_code=303)
