from fastapi import FastAPI
from app.db.database import Base, engine
from app.routers.auth import router as auth_router

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(auth_router)

import os

import requests
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles



app = FastAPI(title="Smart Fridge & Nutrition Coach")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)


@app.get("/")
def auth_page():
    return render_page(
        "Authentification | Smart Fridge",
        "/",
        """
        <section class="card max-w-5xl mx-auto">
            <div class="mb-8">
                <p class="text-sm font-semibold uppercase tracking-[0.2em] text-green-700">Smart Fridge</p>
                <h1 class="mt-2 text-3xl font-black text-slate-900">Connexion & inscription</h1>
            </div>

            <div class="grid gap-6 lg:grid-cols-2">
                <div class="rounded-2xl border border-green-100 bg-green-50 p-6">
                    <h2 class="mb-4 text-2xl font-bold text-slate-900">Se connecter</h2>
                    <form id="login-form" class="space-y-4">
                        <div>
                            <label for="login-email" class="mb-2 block text-sm font-semibold text-slate-700">Email</label>
                            <input id="login-email" name="email" type="email" placeholder="vous@example.com" required class="w-full rounded-xl border border-green-200 bg-white px-4 py-3 outline-none transition focus:border-green-500 focus:ring-2 focus:ring-green-200" />
                        </div>
                        <div>
                            <label for="login-password" class="mb-2 block text-sm font-semibold text-slate-700">Mot de passe</label>
                            <input id="login-password" name="password" type="password" placeholder="••••••••" required class="w-full rounded-xl border border-green-200 bg-white px-4 py-3 outline-none transition focus:border-green-500 focus:ring-2 focus:ring-green-200" />
                        </div>
                        <button type="submit" class="w-full rounded-xl bg-green-700 px-4 py-3 font-semibold text-white transition hover:bg-green-800">
                            Se connecter
                        </button>
                        <div id="login-message" class="hidden rounded-lg border border-green-200 bg-white px-3 py-2 text-sm text-green-700"></div>
                    </form>
                </div>

                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-6">
                    <h2 class="mb-4 text-2xl font-bold text-slate-900">Créer un compte</h2>
                    <form id="register-form" class="space-y-4">
                        <div>
                            <label for="register-email" class="mb-2 block text-sm font-semibold text-slate-700">Email</label>
                            <input id="register-email" name="email" type="email" placeholder="nouveau@example.com" required class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200" />
                        </div>
                        <div>
                            <label for="register-password" class="mb-2 block text-sm font-semibold text-slate-700">Mot de passe</label>
                            <input id="register-password" name="password" type="password" placeholder="Minimum 6 caractères" required class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200" />
                        </div>
                        <button type="submit" class="w-full rounded-xl bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-slate-700">
                            S'inscrire
                        </button>
                        <div id="register-message" class="hidden rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"></div>
                    </form>
                </div>
            </div>
        </section>

        <script>
            async function submitAuthForm(formId, endpoint, messageBoxId, successText) {
                const form = document.getElementById(formId);
                const messageBox = document.getElementById(messageBoxId);
                const submitButton = form.querySelector('button[type="submit"]');

                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const formData = new FormData(form);
                    const payload = Object.fromEntries(formData.entries());

                    submitButton.disabled = true;
                    submitButton.textContent = 'Chargement...';
                    messageBox.classList.add('hidden');

                    try {
                        const response = await fetch(endpoint, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(payload)
                        });

                        const result = await response.json().catch(() => ({}));

                        if (!response.ok) {
                            throw new Error(result.detail || 'Une erreur est survenue.');
                        }

                        if (result.access_token) {
                            localStorage.setItem('smartfridge_token', result.access_token);
                        }

                        messageBox.textContent = successText;
                        messageBox.className = 'rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700';
                        messageBox.classList.remove('hidden');
                        form.reset();
                        setTimeout(() => window.location.href = '/', 900);
                    } catch (error) {
                        messageBox.textContent = error.message;
                        messageBox.className = 'rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700';
                        messageBox.classList.remove('hidden');
                    } finally {
                        submitButton.disabled = false;
                        submitButton.textContent = formId === 'login-form' ? 'Se connecter' : "S'inscrire";
                    }
                });
            }

            submitAuthForm('login-form', '/auth/login', 'login-message', 'Connexion réussie. Redirection en cours...');
            submitAuthForm('register-form', '/auth/register', 'register-message', 'Compte créé avec succès. Redirection en cours...');
        </script>
        """
    )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    
    openapi_schema = FastAPI.openapi(app)

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
USDA_API_KEY = os.getenv("USDA_API_KEY")

fridge_items = []


def get_alerts():
    alerts = []
    for item in fridge_items:
        if item.get("expiration_date"):
            alerts.append(
                {
                    "title": f"{item['name']} à consommer",
                    "message": f"Produit dans le frigo jusqu’au {item['expiration_date']}.",
                }
            )
    if not alerts:
        alerts.append(
            {"title": "Frigo vide", "message": "Ajoutez des produits pour recevoir des alertes."}
        )
    return alerts


def get_nutrition_summary():
    if not fridge_items:
        return {
            "energy": 0,
            "calories": 0,
            "proteines": 0,
            "glucides": 0,
            "lipides": 0,
            "score": "Aucun produit",
        }

    total = {"calories": 0, "proteins": 0, "carbs": 0, "fat": 0}
    for item in fridge_items:
        name = item.get("name", "")
        if not name:
            continue
        data = get_usda_foods(name, limit=1)
        if data:
            product = data[0]
            total["calories"] += float(product.get("calories", 0) or 0)
            total["proteines"] += float(product.get("proteines", 0) or 0)
            total["glucides"] += float(product.get("glucides", 0) or 0)
            total["lipides"] += float(product.get("lipides", 0) or 0)

    return {
        "calories": round(total["calories"]),
        "proteins": round(total["proteins"]),
        "carbs": round(total["carbs"]),
        "fat": round(total["fat"]),
        "score": "Bon équilibre" if total["calories"] else "Aucun produit",
    }


def fetch_json(url: str, params: dict | None = None, timeout: int = 15):
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_usda_foods(query: str, limit: int = 3):
    if not query or not USDA_API_KEY:
        return []

    try:
        data = fetch_json(
            "https://api.nal.usda.gov/fdc/v1/foods/search",
            params={
                "query": query,
                "dataType": ["SR Legacy", "Branded"],
                "pageSize": limit,
                "api_key": USDA_API_KEY,
            },
        )
    except Exception:
        return []

    foods = []
    for item in (data.get("foods") or [])[:limit]:
        nutrients = item.get("foodNutrients", [])
        nutrients_map = {
            (n.get("nutrientName", "") or "").lower(): n.get("value")
            for n in nutrients
            if isinstance(n, dict)
        }
        foods.append(
            {
                "name": item.get("description", "Produit"),
                "category": item.get("foodCategory", "Autre"),
                "calories": item.get("calories", 0),
                "energie": nutrients_map.get("energy", 0),
                "proteines": nutrients_map.get("proteines", 0),
                "glucides": nutrients_map.get("glucides", 0),
                "lipides": nutrients_map.get("lipides", 0),
            }
        )
    return foods


def get_themealdb_recipes(ingredient: str, limit: int = 3):
    if not ingredient:
        return []

    try:
        filtered = fetch_json(
            "https://www.themealdb.com/api/json/v1/1/filter.php",
            params={"i": ingredient},
        )
    except Exception:
        return []

    meals = filtered.get("meals") or []
    result = []

    for meal in meals[:limit]:
        meal_id = meal.get("idMeal")
        if not meal_id:
            continue
        try:
            detail = fetch_json(
                "https://www.themealdb.com/api/json/v1/1/lookup.php",
                params={"i": meal_id},
            )
        except Exception:
            continue

        d = (detail.get("meals") or [{}])[0]
        result.append(
            {
                "name": d.get("strMeal", meal.get("strMeal", "Recette")),
                "time": d.get("strArea", "Inconnu"),
                "difficulty": "Facile",
                "description": d.get("strInstructions", "Aucune description disponible.")[:160],
            }
        )

    return result


def nav(active: str) -> str:
    links = [
        ("/", "Accueil"),
        ("/fridge", "Frigo"),
        ("/products", "Produits"),
        ("/recipes", "Recettes"),
        ("/nutrition", "Nutrition"),
        ("/alerts", "Alertes"),
    ]
    html = []
    for path, label in links:
        is_active = path == active
        classes = (
            'block rounded-xl bg-white/20 px-4 py-3 font-semibold text-white'
            if is_active
            else 'block rounded-xl bg-white/10 px-4 py-3 text-white/90 transition hover:bg-white/15'
        )
        html.append(f'<a href="{path}" class="{classes}">{label}</a>')
    return "".join(html)


def render_page(title: str, active: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>{title}</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script>
                tailwind.config = {{
                    theme: {{
                        extend: {{
                            colors: {{
                                brand: {{
                                    50: '#f0fdf4',
                                    100: '#dcfce7',
                                    600: '#16a34a',
                                    700: '#15803d',
                                    800: '#166534'
                                }}
                            }}
                        }}
                    }}
                }}
            </script>
            <link rel="stylesheet" href="/static/styles.css" />
        </head>
        <body class="bg-green-50 text-slate-800 antialiased">
            <div class="flex min-h-screen flex-col md:flex-row">
                <aside class="w-full bg-gradient-to-b from-green-800 to-green-600 p-6 text-white md:w-64">
                    <div class="mb-8 text-2xl font-black">Smart Fridge</div>
                    <nav class="flex flex-col gap-3">
                        {nav(active)}
                    </nav>
                </aside>
                <main class="flex-1 p-6 md:p-8">
                    <div class="space-y-6">
                        {body}
                    </div>
                </main>
            </div>
        </body>
        </html>
        """
    )


@app.get("/", response_class=HTMLResponse)
def home_page():
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
    return render_page("Accueil", "/", body)


@app.get("/fridge", response_class=HTMLResponse)
def fridge_page():
    items_html = "".join(
        f"""
        <li class="rounded-xl border border-green-100 bg-green-50 p-4">
            <div>
                <strong class="block text-slate-800">{item['name']}</strong>
                <div class="mt-1 text-sm text-slate-500">Quantité : {item['quantity']}</div>
                <div class="mt-1 text-sm text-slate-500">Catégorie : {item['category'] or '—'}</div>
                <div class="mt-1 text-sm text-slate-500">Expiration : {item['expiration_date'] or '—'}</div>
                <div class="mt-1 text-sm text-slate-500">{item['notes'] or 'Aucune note'}</div>
            </div>
        </li>
        """
        for item in fridge_items
    )
    if not items_html:
        items_html = "<li class='rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-slate-500'>Votre frigo est vide pour le moment.</li>"

    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Mon frigo</h1>
            <form method="post" action="/fridge" class="grid gap-4 md:grid-cols-2">
                <div class="flex flex-col gap-2">
                    <label for="name" class="font-semibold text-slate-700">Nom</label>
                    <input id="name" name="name" placeholder="Ex : Lait" required class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none ring-0 focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="quantity" class="font-semibold text-slate-700">Quantité</label>
                    <input id="quantity" name="quantity" type="number" min="1" value="1" required class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="expiration_date" class="font-semibold text-slate-700">Date d’expiration</label>
                    <input id="expiration_date" name="expiration_date" type="date" class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="category" class="font-semibold text-slate-700">Catégorie</label>
                    <input id="category" name="category" placeholder="Ex : Produits laitiers" class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" />
                </div>
                <div class="flex flex-col gap-2 md:col-span-2">
                    <label for="notes" class="font-semibold text-slate-700">Notes</label>
                    <textarea id="notes" name="notes" placeholder="À consommer rapidement ..." class="min-h-[96px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"></textarea>
                </div>
                <div class="md:col-span-2">
                    <button type="submit" class="inline-flex rounded-xl bg-green-700 px-5 py-3 font-semibold text-white transition hover:bg-green-800">Ajouter au frigo</button>
                </div>
            </form>
        </div>
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h2 class="mb-4 text-2xl font-bold text-slate-800">Contenu actuel</h2>
            <ul class="space-y-3">{items_html}</ul>
        </div>
    """
    return render_page("Mon frigo", "/fridge", body)


@app.post("/fridge", response_class=HTMLResponse)
def add_to_fridge(
    name: str = Form(...),
    quantity: int = Form(...),
    expiration_date: str = Form(""),
    category: str = Form(""),
    notes: str = Form(""),
):
    if not name.strip():
        items_html = "".join(
            f"<li class='rounded-xl border border-slate-200 bg-slate-50 p-4'><strong class='block text-slate-800'>{item['name']}</strong><div class='mt-1 text-sm text-slate-500'>{item['quantity']}</div></li>" for item in fridge_items
        )
        body = f"""
            <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
                <h1 class="mb-4 text-3xl font-bold text-slate-800">Mon frigo</h1>
                <p class="mb-4 rounded-xl bg-red-100 px-4 py-3 font-semibold text-red-700">Le nom du produit est obligatoire.</p>
                <ul class="space-y-3">{items_html}</ul>
            </div>
        """
        return render_page("Mon frigo", "/fridge", body)

    fridge_items.append(
        {
            "name": name.strip(),
            "quantity": quantity,
            "expiration_date": expiration_date,
            "category": category.strip(),
            "notes": notes.strip(),
        }
    )
    return fridge_page()


@app.get("/products", response_class=HTMLResponse)
def products_page():
    query = ""
    if fridge_items:
        query = fridge_items[0].get("name", "").strip()

    products_data = get_usda_foods(query, limit=3) if USDA_API_KEY and query else []
    items_html = "".join(
        f"""
        <li class="rounded-xl border border-green-100 bg-green-50 p-4">
            <strong class="block text-slate-800">{product['name']}</strong>
            <div class="mt-1 text-sm text-slate-500">Catégorie : {product['category']}</div>
            <div class="mt-1 text-sm text-slate-500">Calories : {product.get('calories', 0)} kcal</div>
            <div class="mt-1 text-sm text-slate-500">Protéines : {product.get('protein', 0)} g</div>
        </li>
        """
        for product in products_data
    )
    if not items_html:
        items_html = "<li class='rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-slate-500'>Aucun produit trouvé. Ajoutez un aliment dans votre frigo ou recherchez un produit.</li>"

    search_box = f"""
        <form method="get" action="/products" class="mb-5 flex gap-3">
            <input name="q" value="{query}" class="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" placeholder="Rechercher un aliment" />
            <button type="submit" class="rounded-xl bg-green-700 px-4 py-2 text-white">Chercher</button>
        </form>
    """

    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Produits</h1>
            {search_box}
            <ul class="space-y-3">{items_html}</ul>
        </div>
    """
    return render_page("Produits", "/products", body)


@app.get("/recipes", response_class=HTMLResponse)
def recipes_page():
    ingredient = ""
    if fridge_items:
        ingredient = fridge_items[0].get("name", "").strip()

    recipe_data = get_themealdb_recipes(ingredient, limit=3) if ingredient else []
    cards = "".join(
        f"""
        <div class="rounded-xl border border-green-100 bg-green-50 p-5">
            <h3 class="mb-2 text-xl font-semibold text-slate-800">{recipe['name']}</h3>
            <div class="text-sm text-slate-500">Temps : {recipe['time']}</div>
            <div class="text-sm text-slate-500">Difficulté : {recipe['difficulty']}</div>
            <p class="mt-3 text-slate-600">{recipe['description']}</p>
        </div>
        """
        for recipe in recipe_data
    )
    if not cards:
        cards = "<div class='rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-slate-500'>Ajoutez un produit au frigo pour obtenir des recettes correspondantes.</div>"
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Recettes</h1>
            <div class="grid gap-4 md:grid-cols-3">{cards}</div>
        </div>
    """
    return render_page("Recettes", "/recipes", body)


@app.get("/nutrition", response_class=HTMLResponse)
def nutrition_page():
    nutrition_summary = get_nutrition_summary()
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Nutrition</h1>
            <div class="grid gap-4 md:grid-cols-4">
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Calories</h3><p class="mt-2 text-slate-600">{nutrition_summary['calories']} kcal</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Protéines</h3><p class="mt-2 text-slate-600">{nutrition_summary['proteins']} g</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Glucides</h3><p class="mt-2 text-slate-600">{nutrition_summary['carbs']} g</p></div>
                <div class="rounded-xl border border-green-100 bg-green-50 p-4"><h3 class="text-lg font-semibold text-slate-800">Lipides</h3><p class="mt-2 text-slate-600">{nutrition_summary['fat']} g</p></div>
            </div>
            <span class="mt-5 inline-block rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-800">Score global : {nutrition_summary['score']}</span>
        </div>
    """
    return render_page("Nutrition", "/nutrition", body)


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page():
    items = "".join(
        f"""
        <li class="rounded-xl border border-amber-100 bg-amber-50 p-4">
            <strong class="block text-slate-800">{alert['title']}</strong>
            <div class="mt-1 text-sm text-slate-600">{alert['message']}</div>
        </li>
        """
        for alert in get_alerts()
    )
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Alertes</h1>
            <ul class="space-y-3">{items}</ul>
        </div>
    """
    return render_page("Alertes", "/alerts", body)