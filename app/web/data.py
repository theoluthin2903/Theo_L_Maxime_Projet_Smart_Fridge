import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv
try:
    from deep_translator import MyMemoryTranslator
except ImportError:
    MyMemoryTranslator = None

from pydantic import BaseModel
from sqlalchemy import asc

from app.db.database import SessionLocal
from app.db.models import AppDateDB, DailyLogDB, FridgeItemDB, RecipeLeftoverDB, RecipeTranslationDB

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
fridge_items = []

# Cache court pour éviter de rappeler TheMealDB à chaque navigation Frigo ↔ Recettes.
_RECIPE_CACHE: dict[str, tuple[float, list[dict]]] = {}
_RECIPE_CACHE_TTL = 1800  # 30 minutes
_PRODUCT_CACHE: tuple[float, list[dict]] | None = None
_PRODUCT_CACHE_TTL = 3600

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


def get_current_app_date(user_id: int) -> date:
    """Renvoie la date 'actuelle' simulée de l'application pour cet utilisateur
    (initialisée à la vraie date du jour lors du premier appel)."""
    with SessionLocal() as db:
        row = db.query(AppDateDB).filter(AppDateDB.user_id == int(user_id)).first()
        if row is None:
            row = AppDateDB(user_id=int(user_id), current_date=date.today().isoformat())
            db.add(row)
            db.commit()
            db.refresh(row)
        try:
            return date.fromisoformat(row.current_date)
        except ValueError:
            return date.today()


def clear_fridge_items(user_id: int):
    """Supprime tous les produits du frigo d'un utilisateur."""
    with SessionLocal() as db:
        db.query(FridgeItemDB).filter(FridgeItemDB.user_id == int(user_id)).delete()
        db.commit()
    load_fridge_items(user_id)
    return True


def advance_to_next_day(user_id: int):
    """Fait réellement passer l'application au jour suivant pour cet utilisateur :
    1. Sauvegarde le frigo + la nutrition du jour en cours dans Supabase (daily_logs),
       avec log_date = date simulée du jour qui se termine.
    2. Vide entièrement le frigo (nouvelle journée = frigo remis à zéro), ce qui
       remet aussi la nutrition à zéro puisqu'elle est calculée à partir du frigo.
    3. Avance la date simulée de l'application d'un jour (utilisée ensuite comme
       date par défaut dans le menu déroulant des dates d'expiration).
    Renvoie un dict avec la nouvelle date, le nombre de produits retirés du frigo
    et la date de la journée qui vient d'être enregistrée.
    """
    user_id = int(user_id)
    current_date = get_current_app_date(user_id)
    items = load_fridge_items(user_id)

    total_calories = total_proteines = total_glucides = total_lipides = 0.0
    for item in items:
        name = (item.get("name") or "").strip()
        quantity = int(item.get("quantity") or 1)
        if not name:
            continue

        food = get_food_nutrition(name)
        portion_grams = float(food.get("portion_grams", 100) or 100)
        factor = (portion_grams * quantity) / 100.0

        total_calories += float(food.get("calories", 0) or 0) * factor
        total_proteines += float(food.get("proteines", 0) or 0) * factor
        total_glucides += float(food.get("glucides", 0) or 0) * factor
        total_lipides += float(food.get("lipides", 0) or 0) * factor

    with SessionLocal() as db:
        log = DailyLogDB(
            user_id=user_id,
            log_date=current_date.isoformat(),
            fridge_snapshot=json.dumps(items, ensure_ascii=False),
            total_calories=round(total_calories),
            total_proteines=round(total_proteines),
            total_glucides=round(total_glucides),
            total_lipides=round(total_lipides),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.add(log)
        db.commit()

    new_date = current_date + timedelta(days=1)

    cleared_count = 0
    with SessionLocal() as db:
        cleared_count = (
            db.query(FridgeItemDB)
            .filter(FridgeItemDB.user_id == user_id)
            .delete()
        )
        db.commit()

    with SessionLocal() as db:
        date_row = db.query(AppDateDB).filter(AppDateDB.user_id == user_id).first()
        if date_row is None:
            date_row = AppDateDB(user_id=user_id, current_date=new_date.isoformat())
            db.add(date_row)
        else:
            date_row.current_date = new_date.isoformat()
        db.commit()

    load_fridge_items(user_id)

    return {
        "new_date": new_date,
        "expired_removed": cleared_count,
        "log_date": current_date,
    }


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


def fetch_json(url: str, params: dict | None = None, timeout: int = 15):
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()

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


def _extract_usda_energy_kcal(nutrients):
    """Renvoie l'énergie en kcal (jamais en kJ)."""
    kcal_by_id, kj = {}, None
    for n in nutrients:
        if not isinstance(n, dict) or n.get("value") is None:
            continue
        name = (n.get("nutrientName") or "").lower()
        unit = (n.get("unitName") or "").lower()
        if "energy" not in name:
            continue
        if unit == "kcal":
            kcal_by_id[n.get("nutrientId")] = n["value"]
        elif unit == "kj":
            kj = n["value"]
    for nutrient_id in (1008, 2047, 2048):  # Energy, puis Atwater general / specific
        if nutrient_id in kcal_by_id:
            return kcal_by_id[nutrient_id]
    if kcal_by_id:
        return next(iter(kcal_by_id.values()))
    return round(kj / 4.184, 1) if kj is not None else 0


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
                    "pageSize": 200 if limit is None else max(5, limit),
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
                "calories": _extract_usda_energy_kcal(nutrients),
                "energie": _extract_usda_energy_kcal(nutrients),

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
            if limit is not None and len(foods) >= limit:
                return foods

    return foods



def get_available_products(query: str = "", limit: int = None):
    """Catalogue rapide pour le formulaire Frigo, sans rafale d'appels USDA.

    Le catalogue complet TheMealDB est chargé une seule fois puis conservé une
    heure en mémoire. USDA reste utilisé par les fonctions de nutrition, mais
    plus pour construire le menu déroulant à chaque navigation.
    """
    global _PRODUCT_CACHE
    now = time.monotonic()

    if _PRODUCT_CACHE and now - _PRODUCT_CACHE[0] < _PRODUCT_CACHE_TTL:
        products = [dict(product) for product in _PRODUCT_CACHE[1]]
    else:
        products: list[dict] = []
        seen: set[str] = set()
        try:
            meal_db = fetch_json(
                "https://www.themealdb.com/api/json/v1/1/list.php",
                params={"i": "list"},
                timeout=5,
            )
            for ingredient in (meal_db.get("meals") or []):
                name = (ingredient.get("strIngredient") or "").strip()
                key = normalize_name(name)
                if name and key and key not in seen:
                    seen.add(key)
                    products.append({
                        "name": name,
                        "category": _infer_product_category(name, "Ingrédient"),
                    })
        except Exception as exc:
            print(f"[Frigo] Catalogue TheMealDB indisponible : {exc}")

        products.sort(key=lambda item: item["name"].casefold())
        _PRODUCT_CACHE = (now, [dict(product) for product in products])

    if query and query.strip():
        needle = normalize_name(query)
        products = [
            product for product in products
            if needle in normalize_name(product["name"])
        ]

    return products[:limit] if limit is not None else products

def get_available_product_names(query: str = "", limit: int = None):
    products = get_available_products(query=query, limit=limit)
    return [product["name"] for product in products]


# Poids moyen utilisé lorsqu'un aliment du frigo est compté à l'unité.
# Les données USDA sont exprimées pour 100 g : sans cette conversion,
# "2 pommes" était interprété comme 200 g, "2 œufs" comme 200 g, etc.
# Ces valeurs sont volontairement des estimations réalistes et peuvent varier
# selon la taille réelle du produit.
_PRODUCT_PORTION_GRAMS = {
    # Fruits
    "apple": 180, "pomme": 180,
    "banana": 120, "banane": 120,
    "orange": 160, "orange": 160,
    "lemon": 80, "citron": 80,
    "lime": 70, "citron vert": 70,
    "pear": 175, "poire": 175,
    "peach": 150, "peche": 150, "pêche": 150,
    "plum": 70, "prune": 70,
    "kiwi": 75,
    "mango": 200, "mangue": 200,
    "avocado": 150, "avocat": 150,
    "strawberry": 15, "fraise": 15,
    "grape": 5, "raisin": 5,
    "cherry": 8, "cerise": 8,
    "pineapple": 900, "ananas": 900,
    "melon": 800, "watermelon": 3000,
    # Légumes
    "tomato": 120, "tomate": 120,
    "carrot": 60, "carotte": 60,
    "onion": 110, "oignon": 110,
    "garlic": 5, "ail": 5,
    "potato": 170, "pomme de terre": 170,
    "sweet potato": 180, "patate douce": 180,
    "cucumber": 300, "concombre": 300,
    "zucchini": 200, "courgette": 200,
    "eggplant": 450, "aubergine": 450,
    "bell pepper": 150, "pepper": 120, "poivron": 150,
    "mushroom": 18, "champignon": 18,
    "broccoli": 300, "brocoli": 300,
    "cauliflower": 700, "chou fleur": 700,
    "lettuce": 600, "laitue": 600,
    # Œufs / produits laitiers
    "egg": 55, "eggs": 55, "œuf": 55, "oeuf": 55,
    "milk": 240, "lait": 240,
    "yogurt": 125, "yoghurt": 125, "yaourt": 125,
    "butter": 15, "beurre": 15,
    # Viandes / poissons
    "chicken breast": 150, "chicken": 150, "poulet": 150,
    "beef": 150, "boeuf": 150, "bœuf": 150,
    "steak": 180,
    "pork": 150, "porc": 150,
    "ham": 40, "jambon": 40,
    "salmon": 150, "saumon": 150,
    "tuna": 140, "thon": 140,
    "cod": 150, "cabillaud": 150,
    "shrimp": 15, "prawn": 15, "crevette": 15,
    # Féculents / pain
    "bread": 40, "pain": 40,
    "baguette": 250,
    "roll": 60, "bun": 70,
    "rice": 100, "riz": 100,
    "pasta": 100, "pates": 100, "pâtes": 100,
    # Matières grasses / condiments
    "olive oil": 15, "huile d'olive": 15,
    "oil": 15, "huile": 15,
    "mayonnaise": 15, "mayo": 15,
    "ketchup": 15, "mustard": 10, "moutarde": 10,
}

_PRODUCT_CATEGORY_DEFAULT_GRAMS = {
    "Fruits": 150,
    "Légumes": 120,
    "Produits laitiers": 125,
    "Œufs": 55,
    "Viandes et volailles": 150,
    "Poissons et fruits de mer": 150,
    "Féculents et céréales": 100,
    "Pain et boulangerie": 50,
    "Légumineuses": 100,
    "Matières grasses": 15,
    "Herbes et épices": 3,
    "Sauces et condiments": 15,
    "Produits sucrés": 30,
    "Farines et pâtisserie": 30,
    "Fruits à coque et graines": 30,
    "Boissons": 250,
    "Autre": 100,
}

def _estimate_product_portion_grams(name: str, category: str = "Autre") -> float:
    text = normalize_name(name)

    # Les correspondances les plus spécifiques passent en premier.
    for product, grams in sorted(_PRODUCT_PORTION_GRAMS.items(), key=lambda pair: len(pair[0]), reverse=True):
        if normalize_name(product) in text:
            return float(grams)

    return float(_PRODUCT_CATEGORY_DEFAULT_GRAMS.get(category, 100))


def get_food_nutrition(query: str):
    if not query:
        return {
            "name": "",
            "category": "Autre",
            "calories": 0,
            "proteines": 0,
            "glucides": 0,
            "lipides": 0,
            "portion_grams": 100,
            "estimated_portion": True,
        }

    foods = get_usda_foods(query, limit=1)
    if foods:
        food = foods[0]
        category = food.get("category") or "Autre"
        food["portion_grams"] = _estimate_product_portion_grams(query, category)
        food["estimated_portion"] = True
        return food

    return {
        "name": query,
        "category": "Autre",
        "calories": 0,
        "proteines": 0,
        "glucides": 0,
        "lipides": 0,
        "portion_grams": _estimate_product_portion_grams(query, "Autre"),
        "estimated_portion": True,
    }

def _shorten(text: str, max_len: int = 180) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _estimate_recipe_difficulty(recipe: dict) -> str:
    """Estime la difficulté à partir des ingrédients et de la préparation."""
    instructions = (recipe.get("strInstructions") or "").lower()
    ingredient_count = len(flatten_meal_ingredients(recipe))
    score = 0

    if ingredient_count >= 8:
        score += 1
    if ingredient_count >= 13:
        score += 1
    if len(instructions) >= 700:
        score += 1
    if len(instructions) >= 1400:
        score += 1

    advanced_terms = (
        "marinate", "knead", "proof", "reduce", "caramel", "deep fry",
        "bain-marie", "temper", "fillet", "debone", "stuff", "roast",
    )
    score += min(2, sum(term in instructions for term in advanced_terms))

    if score >= 4:
        return "Difficile"
    if score >= 2:
        return "Moyenne"
    return "Facile"


def _recipe_description_fr(recipe: dict) -> str:
    """Crée une courte description en français à partir des métadonnées TheMealDB."""
    category_map = {
        "beef": "bœuf", "chicken": "poulet", "dessert": "dessert",
        "lamb": "agneau", "miscellaneous": "plat varié", "pasta": "pâtes",
        "pork": "porc", "seafood": "fruits de mer", "side": "accompagnement",
        "starter": "entrée", "vegan": "plat végétalien",
        "vegetarian": "plat végétarien", "breakfast": "petit-déjeuner",
        "goat": "chèvre",
    }
    area_map = {
        "american": "américaine", "british": "britannique", "canadian": "canadienne",
        "chinese": "chinoise", "croatian": "croate", "dutch": "néerlandaise",
        "egyptian": "égyptienne", "filipino": "philippine", "french": "française",
        "greek": "grecque", "indian": "indienne", "irish": "irlandaise",
        "italian": "italienne", "jamaican": "jamaïcaine", "japanese": "japonaise",
        "kenyan": "kényane", "malaysian": "malaisienne", "mexican": "mexicaine",
        "moroccan": "marocaine", "polish": "polonaise", "portuguese": "portugaise",
        "russian": "russe", "spanish": "espagnole", "thai": "thaïlandaise",
        "tunisian": "tunisienne", "turkish": "turque", "vietnamese": "vietnamienne",
    }
    category_raw = (recipe.get("strCategory") or "").strip().lower()
    area_raw = (recipe.get("strArea") or "").strip().lower()
    category = category_map.get(category_raw, "plat savoureux")
    area = area_map.get(area_raw)
    ingredient_count = len(flatten_meal_ingredients(recipe))

    if area:
        text = f"Découvrez ce {category} inspiré de la cuisine {area}, simple à préparer à la maison"
    else:
        text = f"Découvrez ce {category}, une recette savoureuse à préparer à la maison"
    if ingredient_count:
        text += f" avec {ingredient_count} ingrédients principaux"
    return text + "."


def get_themealdb_recipes(ingredient: str, limit: int | None = None):
    """Retourne rapidement les recettes TheMealDB correspondant au frigo.

    Les résultats sont gardés 10 minutes en mémoire et les détails des recettes
    sont récupérés en parallèle. Cela évite 10 à 20 appels HTTP séquentiels à
    chaque aller-retour entre les pages Frigo et Recettes.
    """
    if not ingredient:
        return []

    cache_key = f"{ingredient.strip().casefold()}|{limit or 'all'}"
    cached = _RECIPE_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _RECIPE_CACHE_TTL:
        # Une copie évite qu'une page modifie accidentellement le cache.
        return [dict(recipe) for recipe in cached[1]]

    terms = []
    normalized_terms = set()
    for term in ingredient.replace(";", ",").split(","):
        term = term.strip()
        normalized = normalize_name(term)
        if term and normalized and normalized not in normalized_terms:
            terms.append(term)
            normalized_terms.add(normalized)
    if not terms:
        return []

    per_term: dict[str, list[dict]] = {}
    matched_by_meal: dict[str, list[str]] = {}
    meal_info: dict[str, dict] = {}

    # Les recherches par ingrédient sont indépendantes : on les lance ensemble.
    def fetch_for_term(term: str):
        try:
            filtered = fetch_json(
                "https://www.themealdb.com/api/json/v1/1/filter.php",
                params={"i": term.replace(" ", "_")},
                timeout=8,
            )
            return term, [m for m in (filtered.get("meals") or []) if m.get("idMeal")]
        except Exception:
            return term, []

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(terms)))) as executor:
        futures = [executor.submit(fetch_for_term, term) for term in terms]
        for future in as_completed(futures):
            term, meals = future.result()
            per_term[term] = meals
            for meal in meals:
                meal_id = meal["idMeal"]
                meal_info.setdefault(meal_id, meal)
                matched_by_meal.setdefault(meal_id, []).append(term)

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

    # On ne demande les détails que pour le nombre de cartes réellement affiché.
    candidate_ids = ordered[:limit] if limit is not None else ordered

    def fetch_detail(meal_id: str):
        try:
            detail = fetch_json(
                "https://www.themealdb.com/api/json/v1/1/lookup.php",
                params={"i": meal_id},
                timeout=8,
            )
            return meal_id, (detail.get("meals") or [{}])[0]
        except Exception:
            return meal_id, {}

    details_by_id: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(candidate_ids)))) as executor:
        futures = [executor.submit(fetch_detail, meal_id) for meal_id in candidate_ids]
        for future in as_completed(futures):
            meal_id, detail = future.result()
            details_by_id[meal_id] = detail

    result = []
    seen = set()
    for meal_id in candidate_ids:
        d = details_by_id.get(meal_id) or {}
        fallback = meal_info.get(meal_id, {})
        recipe_name = d.get("strMeal") or fallback.get("strMeal") or "Recette"
        normalized_name = normalize_name(recipe_name)
        if not normalized_name or normalized_name in seen:
            continue

        result.append(
            {
                "name": recipe_name,
                "time": _estimate_recipe_time(d),
                "difficulty": _estimate_recipe_difficulty(d),
                "description": _recipe_description_fr(d),
                "instructions": "",
                "meal_id": str(d.get("idMeal") or meal_id),
                "image": d.get("strMealThumb") or fallback.get("strMealThumb") or "",
                "matched": matched_by_meal.get(meal_id, []),
                # Détails bruts TheMealDB gardés pour le calcul de la nutrition
                # réelle de la recette (voir app/web/nutrition_engine.py),
                # sans avoir à refaire un appel HTTP.
                "raw_meal": d or fallback,
            }
        )
        seen.add(normalized_name)

    _RECIPE_CACHE[cache_key] = (now, [dict(recipe) for recipe in result])
    return result


def get_alerts(user_id: int | None = None):
    alerts = []
    items = load_fridge_items(user_id) if user_id is not None else fridge_items
    for item in items:
        if item.get("expiration_date"):
            alerts.append({
                "title": f"{item['name']} à consommer",
                "message": f"Produit dans le frigo jusqu’au {item['expiration_date']}.",
            })

    if user_id is not None:
        with SessionLocal() as db:
            leftovers = db.query(RecipeLeftoverDB).filter(
                RecipeLeftoverDB.user_id == int(user_id), RecipeLeftoverDB.remaining_percent > 0
            ).all()
        for leftover in leftovers:
            alerts.append({
                "title": f"Reste de {leftover.recipe_name}",
                "message": f"Il reste {round(leftover.remaining_percent)}% de la recette (environ {round(leftover.calories_remaining)} kcal) dans votre frigo.",
            })

    if not alerts:
        alerts.append({"title": "Aucune alerte", "message": "Aucun produit ou reste de recette à surveiller pour le moment."})
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