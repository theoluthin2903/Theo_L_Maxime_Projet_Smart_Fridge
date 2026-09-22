from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.layout import get_token_from_request, require_auth, render_page

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    if not get_token_from_request(request):
        return RedirectResponse(url="/login", status_code=302)

    redirect = require_auth(request)
    if redirect:
        return redirect

    body = """
        <section class="space-y-6">
            <div class="overflow-hidden rounded-2xl border border-green-100 bg-white shadow-sm">
                <div class="bg-gradient-to-br from-green-50 via-white to-emerald-50 px-6 py-8 dark:from-slate-800 dark:via-slate-800 dark:to-slate-900 md:px-8">
                    <div class="max-w-3xl">
                        <span class="recipe-tag recipe-tag--fridge">🌿 Smart Fridge</span>
                        <h1 class="mt-4 text-3xl font-extrabold tracking-tight text-slate-800 dark:text-slate-100 md:text-4xl">Bienvenue dans votre Smart Fridge</h1>
                        <p class="mt-3 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300">Gérez vos aliments, évitez le gaspillage et trouvez facilement quoi cuisiner avec les produits déjà présents dans votre frigo.</p>
                        <div class="mt-6 flex flex-wrap gap-3">
                            <a href="/fridge" class="rounded-xl bg-green-700 px-5 py-3 font-bold text-white shadow-sm transition hover:bg-green-800">🧊 Ouvrir mon frigo</a>
                            <a href="/recipes" class="rounded-xl border border-green-200 bg-white px-5 py-3 font-bold text-green-700 shadow-sm transition hover:bg-green-50 dark:border-slate-600 dark:bg-slate-800 dark:text-green-300 dark:hover:bg-slate-700">🍳 Voir les recettes</a>
                        </div>
                    </div>
                </div>
            </div>

            <div>
                <div class="mb-4 flex items-end justify-between gap-4">
                    <div>
                        <p class="text-sm font-bold uppercase tracking-wider text-green-700 dark:text-green-400">Tableau de bord</p>
                        <h2 class="mt-1 text-2xl font-extrabold text-slate-800 dark:text-slate-100">Accès rapides</h2>
                    </div>
                </div>
                <div class="recipe-grid">
                    <a href="/fridge" class="recipe-card group no-underline">
                        <div class="fridge-card__top"><span class="fridge-card__emoji">🧊</span><span class="fridge-card__qty">Frigo</span></div>
                        <div class="recipe-card__body"><h3 class="recipe-card__title">Gérer mon frigo</h3><p class="recipe-card__desc">Ajoutez vos aliments, suivez les quantités et gardez un œil sur les dates de péremption.</p><span class="font-bold text-green-700 dark:text-green-400">Voir mes produits →</span></div>
                    </a>
                    <a href="/recipes" class="recipe-card group no-underline">
                        <div class="fridge-card__top"><span class="fridge-card__emoji">🍳</span><span class="fridge-card__qty">Recettes</span></div>
                        <div class="recipe-card__body"><h3 class="recipe-card__title">Trouver une recette</h3><p class="recipe-card__desc">Découvrez des idées de repas adaptées aux ingrédients disponibles dans votre frigo.</p><span class="font-bold text-green-700 dark:text-green-400">Découvrir les recettes →</span></div>
                    </a>
                    <a href="/nutrition" class="recipe-card group no-underline">
                        <div class="fridge-card__top"><span class="fridge-card__emoji">🥗</span><span class="fridge-card__qty">Nutrition</span></div>
                        <div class="recipe-card__body"><h3 class="recipe-card__title">Suivre ma nutrition</h3><p class="recipe-card__desc">Consultez les informations nutritionnelles et suivez plus facilement votre alimentation.</p><span class="font-bold text-green-700 dark:text-green-400">Voir la nutrition →</span></div>
                    </a>
                    <a href="/alerts" class="recipe-card group no-underline">
                        <div class="fridge-card__top"><span class="fridge-card__emoji">🔔</span><span class="fridge-card__qty">Alertes</span></div>
                        <div class="recipe-card__body"><h3 class="recipe-card__title">Surveiller les alertes</h3><p class="recipe-card__desc">Repérez rapidement les produits à consommer et les informations importantes de votre frigo.</p><span class="font-bold text-green-700 dark:text-green-400">Voir les alertes →</span></div>
                    </a>
                    <a href="/profile" class="recipe-card group no-underline">
                        <div class="profile-card__top"><span class="profile-card__emoji">👤</span><span class="profile-card__qty">Profil</span></div>
                        <div class="profile-card__body"><h3 class="profile-card__title">Voir mon profil</h3><p class="profile-card__desc">Accédez a votre profil pour inspecter et/ou remplir vos informations personnelles.</p><span class="font-bold text-green-700 dark:text-green-400">Voir le profil →</span></div>
                    </a>
                </div>
            </div>
        </section>
    """
    return render_page("Accueil", "/", body, request)
