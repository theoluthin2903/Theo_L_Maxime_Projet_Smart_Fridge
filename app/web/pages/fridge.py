from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

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
        return payload.get("sub")
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
    product_options = get_available_products(limit=200)
    options_html = "".join(
        f'<option value="{product["name"]}" data-category="{product["category"]}">{product["name"]}</option>'
        for product in product_options
    )

    body = f"""
        {visitor_notice}
        <div class="rounded-2xl border border-green-100 bg-white p-6 shadow-sm">
            <h1 class="mb-5 text-3xl font-bold text-slate-800">Mon frigo</h1>
            <form method="post" action="/fridge" class="grid gap-4 md:grid-cols-2">
                <div class="flex flex-col gap-2 md:col-span-2">
                    <label for="product-search" class="font-semibold text-slate-700">Produit</label>
                    <input id="product-search" type="search" placeholder="Rechercher un produit..." class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" {form_disabled} />
                    <select id="name" name="name" required class="mt-2 min-h-[150px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none ring-0 focus:border-green-500" size="10" {form_disabled}>
                        <option value="">Choisir un produit</option>
                        {options_html}
                    </select>
                </div>
                <div class="flex flex-col gap-2">
                    <label for="quantity" class="font-semibold text-slate-700">Quantité</label>
                    <input id="quantity" name="quantity" type="number" min="1" value="1" required class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" {form_disabled} />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="expiration_date" class="font-semibold text-slate-700">Date d’expiration</label>
                    <input id="expiration_date" name="expiration_date" type="date" class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" {form_disabled} />
                </div>
                <div class="flex flex-col gap-2">
                    <label for="category" class="font-semibold text-slate-700">Catégorie</label>
                    <input id="category" name="category" placeholder="Ex : Produits laitiers" class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" {form_disabled} />
                </div>
                <div class="flex flex-col gap-2 md:col-span-2">
                    <label for="notes" class="font-semibold text-slate-700">Notes</label>
                    <textarea id="notes" name="notes" placeholder="À consommer rapidement ..." class="min-h-[96px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none focus:border-green-500" {form_disabled}></textarea>
                </div>
                <div class="md:col-span-2">
                    <button type="submit" class="inline-flex rounded-xl bg-green-700 px-5 py-3 font-semibold text-white transition hover:bg-green-800">{add_button}</button>
                </div>
            </form>
        </div>
        <script>
            const productSearch = document.getElementById('product-search');
            const productSelect = document.getElementById('name');
            const categoryInput = document.getElementById('category');
            if (productSearch && productSelect && categoryInput) {{
                const syncCategory = () => {{
                    const selected = productSelect.selectedOptions[0] || productSelect.options[productSelect.selectedIndex];
                    const category = selected && selected.getAttribute('data-category') ? selected.getAttribute('data-category') : '';
                    categoryInput.value = category;
                }};
                const filterOptions = () => {{
                    const term = productSearch.value.trim().toLowerCase();
                    Array.from(productSelect.options).forEach((option) => {{
                        if (!option.value) {{
                            option.hidden = false;
                            return;
                        }}
                        const optionText = option.text.toLowerCase();
                        option.hidden = term !== '' && !optionText.includes(term);
                    }});
                    const visible = Array.from(productSelect.options).filter((option) => !option.hidden && option.value);
                    if (visible.length > 0) {{
                        productSelect.value = visible[0].value;
                        syncCategory();
                    }} else {{
                        categoryInput.value = '';
                    }}
                }};
                productSelect.addEventListener('change', syncCategory);
                productSelect.addEventListener('input', syncCategory);
                productSelect.addEventListener('click', syncCategory);
                productSelect.addEventListener('keyup', syncCategory);
                productSearch.addEventListener('input', filterOptions);
                filterOptions();
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
        add_fridge_item(name, quantity, int(user_id), expiration_date, category, notes)
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

    products_data = get_usda_foods(query, limit=3) if query else []
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
