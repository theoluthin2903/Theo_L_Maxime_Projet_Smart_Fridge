from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.layout import require_auth, render_page

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    body = """
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Profil</h1>

            <div class="page">
                <div class="card">
                    <h2 class="text-xl font-semibold mb-3">Informations personnelles</h2>
                    <p class="text-slate-600">Ici tu pourras afficher ou modifier ton âge, poids, taille, sexe et objectif.</p>
                </div>

                <div class="card">
                    <h2 class="text-xl font-semibold mb-3">Calcul nutritionnel</h2>
                    <p class="text-slate-600">
                        Cette section affichera ton TMB, calories de maintien, objectif calorique et macros.
                    </p>
                </div>
            </div>
        </div>
    """
    return render_page("Profil", "/profile", body, request)
