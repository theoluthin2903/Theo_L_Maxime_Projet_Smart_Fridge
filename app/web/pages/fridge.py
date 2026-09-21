from datetime import date, datetime, timedelta
from html import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.db.database import SessionLocal
from app.db.models import AdminLogDB, UserDB

from app.web.data import (
    add_fridge_item,
    delete_fridge_item,
    get_available_products,
    get_fridge_search_query,
    get_themealdb_recipes,
    get_usda_foods,
    load_fridge_items,
)
from app.web.layout import require_auth, render_page

router = APIRouter()


def get_user_id_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        from jose import jwt
        from app.core.jwt import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id is not None else None
    except Exception:
        return None


@router.get("/fridge", response_class=HTMLResponse)
def fridge_page(request: Request):
    user_id = get_user_id_from_cookie(request)
    is_logged_in = user_id is not None
    items = load_fridge_items(user_id) if is_logged_in else []
    items_html = "".join(
        f"""
        <li class="rounded-xl border border-green-100 bg-green-50 p-4">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <strong class="block text-slate-800">{item['name']}</strong>
                    <div class="mt-1 text-sm text-slate-500">Quantité : {item['quantity']}</div>
                    <div class="mt-1 text-sm text-slate-500">Catégorie : {item['category'] or '—'}</div>
                    <div class="mt-1 text-sm text-slate-500">Expiration : {item['expiration_date'] or '—'}</div>
                    <div class="mt-1 text-sm text-slate-500">{item['notes'] or 'Aucune note'}</div>
                </div>
                {("<form method='post' action='/fridge/delete'>"
                  f"<input type='hidden' name='item_id' value='{item['id']}' />"
                  "<button type='submit' class='rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-100'>Supprimer</button>"
                  "</form>") if is_logged_in else ""}
            </div>
        </li>
        """
        for item in items
    )
    if not items_html:
        items_html = "<li class='rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-slate-500'>Votre frigo est vide pour le moment.</li>"

    visitor_notice = "" if is_logged_in else """
        <div class="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <p class="font-semibold text-amber-800">Veuillez vous connecter pour compléter votre frigo</p>
            <p class="mt-1 text-sm text-amber-700">
                En mode visiteur, vous pouvez consulter la page, mais vous devez être connecté pour ajouter ou supprimer des aliments.
            </p>
            <a href="/login" class="mt-3 inline-flex rounded-lg bg-green-700 px-4 py-2 text-sm font-semibold text-white hover:bg-green-800">
                Se connecter
            </a>
        </div>
    """
    form_disabled = "" if is_logged_in else "disabled"
    add_button = "Ajouter au frigo" if is_logged_in else "Ajouter au Frigo"
    product_options = get_available_products(limit=None)

    # Menus déroulants du formulaire
    options_html = "".join(
        f'<option value="{escape(product["name"], quote=True)}" '
        f'data-category="{escape(product["category"], quote=True)}">'
        f'{escape(product["name"])}</option>'
        for product in product_options
    )

    categories = sorted(
        {
            (product.get("category") or "Autre").strip()
            for product in product_options
            if (product.get("category") or "").strip()
        },
        key=str.lower,
    )
    category_options_html = "".join(
        f'<option value="{escape(category, quote=True)}">{escape(category)}</option>'
        for category in categories
    )

    quantity_options_html = "".join(
        f'<option value="{quantity}"{" selected" if quantity == 1 else ""}>{quantity}</option>'
        for quantity in range(1, 21)
    )

    today = date.today()
    expiration_options = [("", "Pas de date d’expiration")]
    for offset in range(0, 365):
        expiration_day = today + timedelta(days=offset)
        if offset == 0:
            label = f"Aujourd’hui — {expiration_day.strftime('%d/%m/%Y')}"
        elif offset == 1:
            label = f"Demain — {expiration_day.strftime('%d/%m/%Y')}"
        else:
            label = expiration_day.strftime("%d/%m/%Y")
        expiration_options.append((expiration_day.isoformat(), label))

    expiration_options_html = "".join(
        f'<option value="{value}">{label}</option>'
        for value, label in expiration_options
    )

    note_options = [
        ("", "Aucune note"),
        ("À consommer rapidement", "À consommer rapidement"),
        ("Produit ouvert", "Produit ouvert"),
        ("À congeler", "À congeler"),
        ("Décongelé", "Décongelé"),
        ("Prévu pour une recette", "Prévu pour une recette"),
        ("À partager", "À partager"),
    ]
    note_options_html = "".join(
        f'<option value="{escape(value, quote=True)}">{escape(label)}</option>'
        for value, label in note_options
    )

    body = f"""
        {visitor_notice}
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Mon frigo</h1>
            <form method="post" action="/fridge" class="grid gap-4 md:grid-cols-2">
                <div class="flex flex-col gap-2 md:col-span-2">
                    <label for="name" class="font-semibold text-slate-700">Produit</label>
                    <select id="name" name="name" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"
                        {form_disabled}>
                        <option value="">Choisir un produit</option>
                        {options_html}
                    </select>
                </div>

                <div class="flex flex-col gap-2">
                    <label for="quantity" class="font-semibold text-slate-700">Quantité</label>
                    <select id="quantity" name="quantity" required
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"
                        {form_disabled}>
                        {quantity_options_html}
                    </select>
                </div>

                <div class="flex flex-col gap-2">
                    <label for="expiration_date" class="font-semibold text-slate-700">Date d’expiration</label>
                    <select id="expiration_date" name="expiration_date"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"
                        {form_disabled}>
                        {expiration_options_html}
                    </select>
                </div>

                <div class="flex flex-col gap-2">
                    <label for="category" class="font-semibold text-slate-700">Catégorie</label>
                    <select id="category" name="category"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"
                        {form_disabled}>
                        <option value="">Choisir une catégorie</option>
                        {category_options_html}
                    </select>
                </div>

                <div class="flex flex-col gap-2">
                    <label for="notes" class="font-semibold text-slate-700">Note</label>
                    <select id="notes" name="notes"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500"
                        {form_disabled}>
                        {note_options_html}
                    </select>
                </div>

                <div class="md:col-span-2">
                    <button type="submit"
                        class="inline-flex rounded-xl bg-green-700 px-5 py-3 font-semibold text-white transition hover:bg-green-800">
                        {add_button}
                    </button>
                </div>
            </form>
        </div>

        <script>
            const productSelect = document.getElementById('name');
            const categorySelect = document.getElementById('category');

            if (productSelect && categorySelect) {{
                const syncCategory = () => {{
                    const selected = productSelect.options[productSelect.selectedIndex];
                    const category = selected ? selected.getAttribute('data-category') : '';

                    if (category) {{
                        const matchingOption = Array.from(categorySelect.options).find(
                            (option) => option.value === category
                        );

                        if (matchingOption) {{
                            categorySelect.value = category;
                        }}
                    }}
                }};

                productSelect.addEventListener('change', syncCategory);
            }}
        </script>

        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h2 class="mb-4 text-2xl font-bold text-slate-800">Contenu actuel</h2>
            <ul class="space-y-3">{items_html}</ul>
        </div>
    """
    return render_page("Mon frigo", "/fridge", body, request)


@router.post("/fridge", response_class=HTMLResponse)
def add_to_fridge(
    request: Request,
    name: str = Form(...),
    quantity: int = Form(...),
    expiration_date: str = Form(""),
    category: str = Form(""),
    notes: str = Form(""),
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id_from_cookie(request)

    if not name.strip():
        items = load_fridge_items(user_id)
        items_html = "".join(
            f"<li class='rounded-xl border border-slate-200 bg-slate-50 p-4'><strong class='block text-slate-800'>{item['name']}</strong><div class='mt-1 text-sm text-slate-500'>{item['quantity']}</div></li>" for item in items
        )
        body = f"""
            <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
                <h1 class="mb-4 text-3xl font-bold text-slate-800">Mon frigo</h1>
                <p class="mb-4 rounded-xl bg-red-100 px-4 py-3 font-semibold text-red-700">Le nom du produit est obligatoire.</p>
                <ul class="space-y-3">{items_html}</ul>
            </div>
        """
        return render_page("Mon frigo", "/fridge", body, request)

    if user_id is not None:
        user_id_int = int(user_id)
        add_fridge_item(name, quantity, user_id_int, expiration_date, category, notes)

        # Log de l'ajout : on garde l'utilisateur réel qui a effectué l'action.
        with SessionLocal() as db:
            user = db.query(UserDB).filter(UserDB.id == user_id_int).first()

            details = f"{name.strip()} • quantité : {quantity}"
            if category.strip():
                details += f" • {category.strip()}"
            if expiration_date.strip():
                details += f" • expiration : {expiration_date.strip()}"
            if notes.strip():
                details += f" • note : {notes.strip()}"

            db.add(AdminLogDB(
                admin_user_id=user_id_int,
                action="Produit ajouté au frigo",
                target=name.strip(),
                details=details,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            db.commit()

    return fridge_page(request)


@router.post("/fridge/delete", response_class=HTMLResponse)
def delete_from_fridge(request: Request, item_id: int = Form(...)):
    redirect = require_auth(request)
    if redirect:
        return redirect

    user_id = get_user_id_from_cookie(request)

    if user_id is not None:
        delete_fridge_item(item_id, int(user_id))
    return fridge_page(request)


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    query = get_fridge_search_query()
    if "q" in request.query_params:
        query = request.query_params.get("q", "").strip()

    products_data = get_usda_foods(query, limit = None) if query else []
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
    return render_page("Produits", "/products", body, request)


@router.get("/recipes", response_class=HTMLResponse)
def recipes_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    ingredient = get_fridge_search_query()
    recipe_data = get_themealdb_recipes(ingredient, limit=12) if ingredient else []

    def recipe_card(recipe):
        image = (
            f'<img class="recipe-card__img" src="{escape(recipe["image"])}/preview" alt="{escape(recipe["name"])}" loading="lazy">'
            if recipe.get("image")
            else ""
        )
        tags = "".join(
            f'<span class="recipe-tag recipe-tag--fridge">🧊 {escape(name)}</span>'
            for name in recipe.get("matched", [])
        )
        instructions = escape(recipe.get("instructions") or "")
        details = (
            f'<details class="recipe-card__details"><summary>Voir la préparation</summary><p>{instructions}</p></details>'
            if instructions
            else ""
        )
        return f"""
        <article class="recipe-card">
            {image}
            <div class="recipe-card__body">
                <h3 class="recipe-card__title">{escape(recipe['name'])}</h3>
                <div class="recipe-card__meta">
                    <span class="recipe-tag">⏱ {escape(recipe['time'])}</span>
                    <span class="recipe-tag">👍 {escape(recipe['difficulty'])}</span>
                </div>
                <div class="recipe-card__meta">{tags}</div>
                <p class="mt-3 text-sm text-slate-600 dark:text-slate-300">{escape(recipe.get('description') or '')}</p>
                {details}
            </div>
        </article>
        """

    cards = "".join(recipe_card(recipe) for recipe in recipe_data)
    if not cards:
        cards = "<div class='rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-slate-500'>Ajoutez un produit au frigo pour obtenir des recettes correspondantes.</div>"
    body = f"""
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Recettes</h1>
            <div class="recipe-grid">{cards}</div>
        </div>
    """
    return render_page("Recettes", "/recipes", body, request)


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    from app.web.data import get_alerts

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
    return render_page("Alertes", "/alerts", body, request)