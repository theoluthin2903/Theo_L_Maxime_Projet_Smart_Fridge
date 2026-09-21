from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.data import get_alerts
from app.web.layout import require_auth, render_page

router = APIRouter()


def _alerts_body():
    alerts = get_alerts()
    cards = "".join(
        f"""
        <article class="recipe-card">
            <div class="fridge-card__top">
                <span class="fridge-card__emoji" aria-hidden="true">🔔</span>
                
                <span class="fridge-card__qty">À surveiller</span>
            </div>
            <div class="recipe-card__body">
                <h3 class="recipe-card__title">{alert['title']}</h3>
                <p class="recipe-card__desc">{alert['message']}</p>
            </div>
        </article>
        """
        for alert in alerts
    )
    return f"""
        <section class="space-y-6">
            <div class="overflow-hidden rounded-2xl border border-green-100 bg-white shadow-sm">
                <div class="bg-gradient-to-br from-green-50 via-white to-emerald-50 px-6 py-7 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900 md:px-8">
                    <span class="recipe-tag recipe-tag--fridge">🔔 Centre d'alertes</span>
                    <h1 class="mt-4 text-3xl font-extrabold text-slate-800 dark:text-slate-100">Alertes de votre frigo</h1>
                    <p class="mt-2 max-w-2xl text-slate-600 dark:text-slate-300">Retrouvez ici les produits à surveiller pour mieux anticiper leur consommation et limiter le gaspillage.</p>
                    <div class="mt-5 flex flex-wrap gap-2">
                        <span class="recipe-tag">📋 {len(alerts)} alerte(s)</span>
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
    return render_page("Alertes", "/alerts", _alerts_body(), request)
