from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.data import get_alerts
from app.web.layout import require_auth, render_page
from app.web.pages.fridge import get_user_id_from_cookie

router = APIRouter()


def _alerts_body(user_id=None):
    alerts = get_alerts(user_id)

    level_classes = {
        "danger": "alert-card--danger",
        "urgent": "alert-card--urgent",
        "warning": "alert-card--warning",
        "info": "alert-card--info",
        "success": "alert-card--success",
    }
    badge_classes = {
        "danger": "bg-red-600 text-white", "urgent": "bg-orange-500 text-white",
        "warning": "bg-amber-400 text-amber-950", "info": "bg-sky-600 text-white",
        "success": "bg-green-600 text-white",
    }
    cards = ""
    for alert in alerts:
        level = alert.get("level", "info")
        cards += f"""
        <article class="recipe-card border {level_classes.get(level, level_classes['info'])}">
            <div class="fridge-card__top">
                <span class="fridge-card__emoji" aria-hidden="true">{alert.get('icon', '🔔')}</span>
                <span class="rounded-full px-3 py-1 text-xs font-bold {badge_classes.get(level, badge_classes['info'])}">{alert.get('badge', 'À surveiller')}</span>
            </div>
            <div class="recipe-card__body">
                <h3 class="recipe-card__title">{alert['title']}</h3>
                <p class="recipe-card__desc">{alert['message']}</p>
            </div>
        </article>
        """
    danger_count = sum(1 for a in alerts if a.get("level") == "danger")
    return f"""
        <section class="space-y-6">
            <div class="overflow-hidden rounded-2xl border border-green-100 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <div class="bg-gradient-to-br from-green-50 via-white to-emerald-50 px-6 py-7 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900 md:px-8">
                    <span class="recipe-tag recipe-tag--fridge">🔔 Centre d'alertes</span>
                    <h1 class="mt-4 text-3xl font-extrabold text-slate-800 dark:text-slate-100">Alertes intelligentes</h1>
                    <p class="mt-2 max-w-2xl text-slate-600 dark:text-slate-300">Les alertes apparaissent seulement quand une action devient utile : péremption proche, reste de recette ou objectif nutritionnel atteint/dépassé.</p>
                    <div class="mt-5 flex flex-wrap gap-2">
                        <span class="recipe-tag">📋 {len(alerts)} alerte(s)</span>
                        {f'<span class="recipe-tag recipe-tag--danger">🚨 {danger_count} urgente(s)</span>' if danger_count else ''}
                        <a href="/fridge" class="recipe-tag recipe-tag--fridge no-underline">🧊 Voir mon frigo →</a>
                    </div>
                </div>
            </div>
            <div class="recipe-grid">{cards}</div>
        </section>
    """


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    return render_page("Alertes", "/alerts", _alerts_body(get_user_id_from_cookie(request)), request)
