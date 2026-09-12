from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.layout import require_auth, render_page

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    body = """
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-3 text-3xl font-bold text-slate-800">Bienvenue dans votre Smart Fridge</h1>
            <p class="mb-6 text-slate-600">Gérez votre frigo, suivez votre nutrition et découvrez des recettes utiles à partir des produits que vous avez.</p>
            <div class="grid gap-4 md:grid-cols-3">
                <div class="rounded-xl border border-green-100 bg-green-50 p-5">
                    <h3 class="mb-2 text-xl font-semibold text-slate-800">Frigo</h3>
                    <p class="text-slate-600">Ajoutez, suivez et consommez les produits avant leur date de péremption.</p>
                </div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-5">
                    <h3 class="mb-2 text-xl font-semibold text-slate-800">Nutrition</h3>
                    <p class="text-slate-600">Visualisez vos apports et recevez des recommandations simples.</p>
                </div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-5">
                    <h3 class="mb-2 text-xl font-semibold text-slate-800">Recettes</h3>
                    <p class="text-slate-600">Créez des idées de repas en fonction de ce que vous avez déjà.</p>
                </div>
            </div>
        </div>
    """
    return render_page("Accueil", "/", body, request)
