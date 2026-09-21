import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import asc

from app.db.database import SessionLocal
from app.db.models import FridgeItemDB

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
fridge_items = []


def _translate_instructions_fr(text: str) -> str:
    """Traduit une préparation avec MyMemory. La persistance est gérée dans Supabase."""
    clean_text = (text or "").strip()
    if not clean_text:
        return "Préparation non disponible."
    if MyMemoryTranslator is None:
        return clean_text

    chunks: list[str] = []
    remaining = clean_text
    while remaining:
        if len(remaining) <= 450:
            chunks.append(remaining)
            break
        cut = max(remaining.rfind(". ", 0, 450), remaining.rfind("\n", 0, 450))
        if cut < 120:
            cut = 450
        else:
            cut += 1
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    try:
        translator = MyMemoryTranslator(source="en-GB", target="fr-FR")
        translated_parts = [
            (translator.translate(chunk) or chunk).strip()
            for chunk in chunks
        ]
        translated = "\n\n".join(translated_parts).strip()
        return translated or clean_text
    except Exception as exc:
        print(f"[Traduction recettes] Échec MyMemory : {exc}")
        return clean_text


def get_recipe_instructions_fr(meal_id: str) -> str:
    """Retourne la traduction Supabase existante ou la crée une seule fois."""
    meal_id = str(meal_id).strip()
    if not meal_id:
        return "Préparation non disponible."

    with SessionLocal() as db:
        saved = (
            db.query(RecipeTranslationDB)
            .filter(
                RecipeTranslationDB.meal_id == meal_id,
                RecipeTranslationDB.target_language == "fr",
            )
            .first()
        )
        if saved and saved.translated_text:
            return saved.translated_text

    detail = fetch_json(
        "https://www.themealdb.com/api/json/v1/1/lookup.php",
        params={"i": meal_id},
    )
    meal = (detail.get("meals") or [{}])[0]
    original = (meal.get("strInstructions") or "").strip()
    if not original:
        return "Préparation non disponible."

    translated = _translate_instructions_fr(original)

    # Ne mémorise pas un échec de traduction : un prochain essai pourra retenter.
    if not translated or translated.casefold() == original.casefold():
        return original

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with SessionLocal() as db:
        # Nouvelle vérification pour éviter les doublons si deux requêtes arrivent ensemble.
        saved = (
            db.query(RecipeTranslationDB)
            .filter(
                RecipeTranslationDB.meal_id == meal_id,
                RecipeTranslationDB.target_language == "fr",
            )
            .first()
        )
        if saved:
            return saved.translated_text

        db.add(RecipeTranslationDB(
            meal_id=meal_id,
            recipe_name=(meal.get("strMeal") or "").strip() or None,
            source_language="en",
            target_language="fr",
            original_text=original,
            translated_text=translated,
            created_at=now,
            updated_at=now,
        ))
        db.commit()

    return translated


def load_fridge_items(user_id: int | None = None):
    global fridge_items
    with SessionLocal() as db:
        query = db.query(FridgeItemDB)
        if user_id is not None:
            query = query.filter(FridgeItemDB.user_id == int(user_id))
        fridge_items = [
            {
                "id": item.id,
                "user_id": item.user_id,
                "name": item.name,
                "quantity": item.quantity,
                "expiration_date": item.expiration_date or "",
                "category": item.category or "",
                "notes": item.notes or "",
            }
            for item in query.order_by(asc(FridgeItemDB.id)).all()
        ]
    return fridge_items


def add_fridge_item(
    name: str,
    quantity: int,
    user_id: int,
    expiration_date: str = "",
    category: str = "",
    notes: str = "",
):
    clean_name = (name or "").strip()
    if not clean_name:
        return None

    with SessionLocal() as db:
        item = FridgeItemDB(
            user_id=int(user_id),
            name=clean_name,
            quantity=int(quantity or 1),
            expiration_date=expiration_date or "",
            category=(category or "").strip(),
            notes=(notes or "").strip(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        created = {
            "id": item.id,
            "user_id": item.user_id,
            "name": item.name,
            "quantity": item.quantity,
            "expiration_date": item.expiration_date or "",
            "category": item.category or "",
            "notes": item.notes or "",
        }

    load_fridge_items(user_id)
    return created


def delete_fridge_item(item_id: int, user_id: int | None = None):
    with SessionLocal() as db:
        query = db.query(FridgeItemDB).filter(FridgeItemDB.id == int(item_id))
        if user_id is not None:
            query = query.filter(FridgeItemDB.user_id == int(user_id))
        deleted = query.first()
        if deleted:
            db.delete(deleted)
            db.commit()
    load_fridge_items(user_id)
    return True


class IngredientQuantity(BaseModel):
    ingredient: str
    quantity: str = ""
    normalized: str = ""

    @classmethod
    def from_pair(cls, ingredient: str, quantity: str = ""):
        cleaned = (ingredient or "").strip()
        return cls(
            ingredient=cleaned,
            quantity=(quantity or "").strip(),
            normalized=normalize_name(cleaned),
        )


def normalize_name(name: str) -> str:
    return (name or "").strip().lower().replace("-", " ")


def flatten_meal_ingredients(meal: dict) -> list[IngredientQuantity]:
    ingredients: list[IngredientQuantity] = []
    seen = set()

    for index in range(1, 21):
        ingredient = (meal.get(f"strIngredient{index}") or "").strip()
        if not ingredient:
            continue

        normalized = normalize_name(ingredient)
        if not normalized or normalized in seen:
            continue

        quantity = (meal.get(f"strMeasure{index}") or "").strip()
        ingredients.append(IngredientQuantity.from_pair(ingredient, quantity))
        seen.add(normalized)

    return ingredients


def get_fridge_ingredient_names():
    names = []
    for item in fridge_items:
        name = (item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def get_fridge_search_query():
    names = get_fridge_ingredient_names()
    return ", ".join(names) if names else ""


_session = requests.Session()  # réutilise les connexions HTTP (évite un handshake TLS à chaque appel)
_CACHE: dict = {}


def _cached(key, ttl, compute, cache_empty=True):
    """Cache mémoire simple : recalcule seulement si l'entrée a plus de `ttl` secondes."""
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = compute()
    if value or cache_empty:
        _CACHE[key] = (now, value)
    return value


def fetch_json(url: str, params: dict | None = None, timeout: int = 15):
    response = _session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _extract_nutrient_value(nutrients, names):
    normalized = {
        (n.get("nutrientName", "") or "").strip().lower().replace("-", " "): n.get("value")
        for n in nutrients
        if isinstance(n, dict)
    }
    for candidate in names:
        exact = normalized.get(candidate.strip().lower())
        if exact is not None:
            return exact
    return 0


def _extract_usda_nutrient_value(nutrients, names=None, nutrient_ids=None):
    names = names or []
    nutrient_ids = nutrient_ids or []
    normalized = {
        (n.get("nutrientName", "") or "").strip().lower().replace("-", " "): n.get("value")
        for n in nutrients
        if isinstance(n, dict)
    }
    for candidate in names:
        value = normalized.get(candidate.strip().lower())
        if value is not None:
            return value

    for nutrient_id in nutrient_ids:
        for item in nutrients:
            if isinstance(item, dict) and int(item.get("nutrientId", -1) or -1) == int(nutrient_id):
                return item.get("value")
    return 0


def _normalize_category(category: str):
    """Normalise une catégorie brute provenant d'une API."""
    value = (category or "").strip()
    lowered = value.lower()

    if any(keyword in lowered for keyword in ["fruit"]):
        return "Fruits"
    if any(keyword in lowered for keyword in ["vegetable", "vegetables", "tomato"]):
        return "Légumes"
    if any(keyword in lowered for keyword in ["dairy", "milk", "cheese", "yogurt"]):
        return "Produits laitiers"
    if any(keyword in lowered for keyword in ["egg"]):
        return "Œufs"
    if any(keyword in lowered for keyword in ["beef", "meat", "poultry", "chicken", "pork", "lamb"]):
        return "Viandes et volailles"
    if any(keyword in lowered for keyword in ["fish", "seafood", "shellfish"]):
        return "Poissons et fruits de mer"
    if any(keyword in lowered for keyword in ["grain", "cereal", "rice", "pasta"]):
        return "Féculents et céréales"
    if any(keyword in lowered for keyword in ["bread", "bakery"]):
        return "Pain et boulangerie"
    if any(keyword in lowered for keyword in ["legume", "bean", "lentil", "pea"]):
        return "Légumineuses"
    if any(keyword in lowered for keyword in ["dessert", "sweets", "cookie", "cake", "chocolate", "candy"]):
        return "Produits sucrés"
    if any(keyword in lowered for keyword in ["beverage", "drink", "juice"]):
        return "Boissons"
    if any(keyword in lowered for keyword in ["oil", "fat", "butter", "margarine"]):
        return "Matières grasses"

    return value or "Autre"


def _infer_product_category(name: str, raw_category: str = "") -> str:
    """Déduit automatiquement une catégorie cohérente depuis le nom du produit."""
    text = normalize_name(name)
    raw = (raw_category or "").strip()

    category_keywords = [
        ("Fruits", [
            "apple", "banana", "orange", "lemon", "lime", "pear", "peach",
            "apricot", "plum", "grape", "strawberry", "raspberry", "blueberry",
            "blackberry", "cherry", "mango", "pineapple", "kiwi", "melon",
            "watermelon", "coconut", "avocado", "fig", "date", "pomegranate",
        ]),
        ("Légumes", [
            "tomato", "carrot", "onion", "garlic", "potato", "sweet potato",
            "cucumber", "lettuce", "salad", "spinach", "broccoli", "cauliflower",
            "cabbage", "zucchini", "courgette", "eggplant", "aubergine",
            "pepper", "bell pepper", "mushroom", "celery", "leek", "beet",
            "radish", "asparagus", "artichoke", "pumpkin", "squash", "corn",
        ]),
        ("Produits laitiers", [
            "milk", "cheese", "yogurt", "yoghurt", "cream", "creme",
            "mozzarella", "parmesan", "cheddar", "ricotta", "feta",
            "mascarpone", "cottage cheese",
        ]),
        ("Œufs", ["egg", "eggs"]),
        ("Viandes et volailles", [
            "chicken", "turkey", "beef", "steak", "pork", "ham", "bacon",
            "lamb", "veal", "duck", "sausage", "minced meat", "ground beef",
        ]),
        ("Poissons et fruits de mer", [
            "fish", "salmon", "tuna", "cod", "haddock", "trout", "sardine",
            "mackerel", "shrimp", "prawn", "crab", "lobster", "mussel",
            "oyster", "clam", "squid", "octopus", "anchovy",
        ]),
        ("Féculents et céréales", [
            "rice", "pasta", "spaghetti", "macaroni", "noodle", "couscous",
            "quinoa", "bulgur", "oat", "oats", "barley", "wheat", "semolina",
            "polenta", "cereal",
        ]),
        ("Pain et boulangerie", [
            "bread", "baguette", "bun", "roll", "tortilla", "pita", "croissant",
            "brioche", "toast",
        ]),
        ("Légumineuses", [
            "lentil", "lentils", "bean", "beans", "chickpea", "chickpeas",
            "pea", "peas", "kidney bean", "black bean", "soybean",
        ]),
        ("Herbes et épices", [
            "parsley", "basil", "thyme", "rosemary", "oregano", "coriander",
            "cilantro", "mint", "sage", "dill", "paprika", "cumin", "curry",
            "turmeric", "cinnamon", "nutmeg", "ginger", "peppercorn", "chili",
            "chilli", "vanilla", "saffron",
        ]),
        ("Sauces et condiments", [
            "mustard", "ketchup", "mayonnaise", "mayo", "soy sauce", "vinegar",
            "sauce", "pesto", "relish", "stock", "broth", "bouillon",
        ]),
        ("Matières grasses", [
            "butter", "margarine", "olive oil", "oil", "coconut oil",
            "sunflower oil", "rapeseed oil",
        ]),
        ("Produits sucrés", [
            "sugar", "chocolate", "honey", "jam", "jelly", "caramel",
            "cookie", "biscuit", "cake", "candy", "syrup", "ice cream",
        ]),
        ("Farines et pâtisserie", [
            "flour", "baking powder", "baking soda", "yeast", "cornstarch",
            "cocoa powder",
        ]),
        ("Fruits à coque et graines", [
            "almond", "walnut", "hazelnut", "cashew", "pistachio", "peanut",
            "pecan", "sesame", "chia", "flax", "sunflower seed", "pumpkin seed",
        ]),
        ("Boissons", [
            "water", "juice", "coffee", "tea", "soda", "lemonade",
            "smoothie", "drink",
        ]),
    ]

    for category, keywords in category_keywords:
        if any(keyword in text for keyword in keywords):
            return category

    normalized_raw = _normalize_category(raw)
    if normalized_raw.lower() in {"ingrédient", "ingredient", "autre"}:
        return "Autre"

    return normalized_raw


def _estimate_recipe_time(recipe: dict):
    instructions = (recipe.get("strInstructions") or "")
    category = (recipe.get("strCategory") or "").lower()
    length = len(instructions)

    if "breakfast" in category:
        return "15 min"
    if "dessert" in category:
        return "45 min"
    if "side" in category:
        return "20 min"
    if "beef" in category or "chicken" in category:
        return "35 min"
    if length < 350:
        return "20 min"
    if length < 800:
        return "35 min"
    return "45 min"


def get_usda_foods(query: str, limit: int = None):
    if not query:
        return []

    normalized_terms = [term.strip() for term in query.replace(";", ",").split(",") if term.strip()]
    if not normalized_terms:
        return []

    if not USDA_API_KEY:
        return []

    foods = []
    seen = set()

    for term in normalized_terms:
        try:
            data = fetch_json(
                "https://api.nal.usda.gov/fdc/v1/foods/search",
                params={
                    "query": term,
                    "dataType": ["SR Legacy", "Foundation"],
                    "pageSize": max(5, limit),
                    "api_key": USDA_API_KEY,
                },
            )
        except Exception:
            continue

        for item in (data.get("foods") or []):
            product_name = item.get("description", "Produit")
            unique_key = normalize_name(product_name)
            if not unique_key or unique_key in seen:
                continue

            nutrients = item.get("foodNutrients", [])
            candidate = {
                "name": product_name,
                "category": _normalize_category(item.get("foodCategory", "Autre")),
                "calories": _extract_usda_nutrient_value(
                    nutrients,
                    ["energy", "energy, total", "energ", "calories"],
                    [1008],
                ),
                "energie": _extract_usda_nutrient_value(
                    nutrients,
                    ["energy", "energy, total", "energ", "calories"],
                    [1008],
                ),
                "proteines": _extract_usda_nutrient_value(
                    nutrients,
                    ["protein", "proteins"],
                    [1003],
                ),
                "glucides": _extract_usda_nutrient_value(
                    nutrients,
                    ["carbohydrate, by difference", "carbohydrate", "carbohydrates", "total carbohydrate"],
                    [1005],
                ),
                "lipides": _extract_usda_nutrient_value(
                    nutrients,
                    ["total lipid (fat)", "fat", "lipids", "total fat"],
                    [1004],
                ),
            }
            foods.append(candidate)
            seen.add(unique_key)
            if len(foods) >= limit:
                return foods

    return foods



def get_available_products(query: str = "", limit: int = None):
    return _cached(
        ("products", query, limit),
        3600,
        lambda: _build_available_products(query, limit),
        cache_empty=False,  # si les APIs sont en panne, on réessaie au prochain chargement
    )


def _build_available_products(query: str = "", limit: int = None):
    """Retourne les produits réellement renvoyés par les APIs, sans données codées en dur."""
    products: list[dict] = []
    seen: set[str] = set()

    def add_product(name: str, category: str = "Autre"):
        cleaned = (name or "").strip()
        if not cleaned:
            return
        key = normalize_name(cleaned)
        if key and key not in seen:
            seen.add(key)
            products.append({
                "name": cleaned,
                "category": _infer_product_category(cleaned, category),
            })

    search_terms = [query.strip()] if query and query.strip() else [
        "milk", "apple", "tomato", "chicken", "bread", "rice", "egg", "cheese",
        "fish", "pasta", "banana", "yogurt", "beef", "salad", "mushroom",
        "carrot", "lentil", "bean", "orange", "onion", "garlic", "potato",
        "spinach", "lemon", "olive", "pepper", "salmon", "shrimp", "tuna",
        "chickpea", "lentils", "mustard", "butter", "flour", "sugar", "oil",
        "cucumber", "lettuce", "broccoli", "pear", "strawberry", "parsley",
        "thyme", "basil", "paprika", "vanilla", "chocolate"
    ]

    terms = [(t or "").strip() for t in search_terms if (t or "").strip()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda t: get_usda_foods(t, limit), terms))  # garde l'ordre

    for foods in results:
        for item in foods:
            add_product(item.get("name", ""), item.get("category", "Autre"))

    try:
        meal_db = fetch_json(
            "https://www.themealdb.com/api/json/v1/1/list.php",
            params={"i": "list"},
            timeout=8,
        )
        for ingredient in (meal_db.get("meals") or []):
            ingredient_name = (ingredient.get("strIngredient") or "").strip()
            if ingredient_name:
                add_product(ingredient_name, "Ingrédient")
    except Exception:
        pass

    if query:
        filtered = [
            product for product in products
            if normalize_name(query) in normalize_name(product["name"]) or normalize_name(product["name"]) in normalize_name(query)
        ]
        return filtered[:limit]

    return sorted(products, key=lambda item: item["name"].lower())[:limit]


def get_available_product_names(query: str = "", limit: int = None):
    products = get_available_products(query=query, limit=limit)
    return [product["name"] for product in products]


def get_food_nutrition(query: str):
    if not query:
        return {
            "name": "",
            "category": "Autre",
            "calories": 0,
            "proteines": 0,
            "glucides": 0,
            "lipides": 0,
        }

    foods = get_usda_foods(query, limit=1)
    if foods:
        return foods[0]

    return {
        "name": query,
        "category": "Autre",
        "calories": 0,
        "proteines": 0,
        "glucides": 0,
        "lipides": 0,
    }

def _shorten(text: str, max_len: int = 180) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _translate(text: str) -> str:
    """Utilise translate_text() si vous l'avez ajouté, sinon renvoie le texte tel quel."""
    fn = globals().get("translate_text")
    return fn(text) if fn else text


def _fetch_meals_for_term(term: str) -> list[dict]:
    def compute():
        data = fetch_json(
            "https://www.themealdb.com/api/json/v1/1/filter.php",
            params={"i": term.replace(" ", "_")},
        )
        return [m for m in (data.get("meals") or []) if m.get("idMeal")]

    try:
        return _cached(("filter", normalize_name(term)), 86400, compute)
    except Exception:
        return []


def _load_recipe(meal_id: str):
    def compute():
        detail = fetch_json(
            "https://www.themealdb.com/api/json/v1/1/lookup.php",
            params={"i": meal_id},
        )
        d = (detail.get("meals") or [{}])[0]
        instructions = (d.get("strInstructions") or "").strip()
        instructions_fr = _translate(instructions)  # retirez si vous n'avez pas la traduction
        return {
            "raw_name": d.get("strMeal", ""),
            "name": _translate(d.get("strMeal", "Recette")),
            "time": _estimate_recipe_time(d),
            "difficulty": "Facile",
            "description": _shorten(instructions_fr) or "Aucune description disponible.",
            "instructions": instructions_fr,
            "image": d.get("strMealThumb") or "",
        }

    try:
        return _cached(("recipe", meal_id), 86400, compute)
    except Exception:
        return None


def get_themealdb_recipes(ingredient: str, limit: int | None = None):
    if not ingredient:
        return []

    terms = []
    for term in ingredient.replace(";", ",").split(","):
        term = term.strip()
        if term and normalize_name(term) not in [normalize_name(t) for t in terms]:
            terms.append(term)
    if not terms:
        return []

    # 1) une requête par produit, en parallèle (et mises en cache 24 h)
    with ThreadPoolExecutor(max_workers=8) as pool:
        meals_lists = list(pool.map(_fetch_meals_for_term, terms))
    per_term = dict(zip(terms, meals_lists))

    matched_by_meal: dict[str, list[str]] = {}
    for term, meals in per_term.items():
        for meal in meals:
            matched_by_meal.setdefault(meal["idMeal"], []).append(term)

    # 2) ordre : recettes multi-produits d'abord, puis alternance entre produits
    ordered = sorted(
        (mid for mid, matched in matched_by_meal.items() if len(matched) > 1),
        key=lambda mid: -len(matched_by_meal[mid]),
    )
    max_len = max((len(m) for m in per_term.values()), default=0)
    for index in range(max_len):
        for term in terms:
            meals = per_term.get(term, [])
            if index < len(meals) and meals[index]["idMeal"] not in ordered:
                ordered.append(meals[index]["idMeal"])

    # 3) détails (+ traduction) des recettes retenues, en parallèle et en cache
    candidates = ordered if limit is None else ordered[: limit + 4]  # +4 = marge pour les échecs/doublons
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(_load_recipe, candidates))

    result, seen = [], set()
    for meal_id, recipe in zip(candidates, loaded):
        if recipe is None:
            continue
        key = normalize_name(recipe["raw_name"])
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({**recipe, "matched": matched_by_meal.get(meal_id, [])})
        if limit is not None and len(result) >= limit:
            break
    return result


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
        alerts.append({"title": "Frigo vide", "message": "Ajoutez des produits pour recevoir des alertes."})
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
        name = (item.get("name") or "").strip()
        if not name:
            continue
        data = get_usda_foods(name, limit=1)
        if data:
            product = data[0]
            total["calories"] += float(product.get("calories", 0) or 0)
            total["proteins"] += float(product.get("proteines", 0) or 0)
            total["carbs"] += float(product.get("glucides", 0) or 0)
            total["fat"] += float(product.get("lipides", 0) or 0)

    return {
        "calories": round(total["calories"]),
        "proteins": round(total["proteins"]),
        "carbs": round(total["carbs"]),
        "fat": round(total["fat"]),
        "score": "Bon équilibre" if total["calories"] else "Aucun produit",
    }