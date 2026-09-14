import os

import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import asc

from app.db.database import SessionLocal
from app.db.models import FridgeItemDB

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
fridge_items = []


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


def fetch_json(url: str, params: dict | None = None, timeout: int = 15):
    response = requests.get(url, params=params, timeout=timeout)
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
    value = (category or "").strip()
    lowered = value.lower()

    if any(keyword in lowered for keyword in ["fruit", "vegetable", "vegetables", "legume", "tomato"]):
        return "Fruits et légumes"
    if any(keyword in lowered for keyword in ["dairy", "milk", "egg", "cheese", "yogurt"]):
        return "Produits laitiers"
    if any(keyword in lowered for keyword in ["beef", "meat", "poultry", "fish", "seafood"]):
        return "Viandes et poissons"
    if any(keyword in lowered for keyword in ["grain", "bread", "cereal", "flour", "pasta"]):
        return "Céréales et grains"
    if any(keyword in lowered for keyword in ["dessert", "sweets", "cookie", "cake"]):
        return "Desserts"
    return value or "Autre"


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


def get_usda_foods(query: str, limit: int = 3):
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



# Valeurs locales de secours pour les aliments courants.
LOCAL_NUTRITION = {
    "lait": {"name": "Lait", "category": "Produits laitiers", "calories": 122, "proteines": 8.1, "glucides": 12.0, "lipides": 4.8},
    "pomme": {"name": "Pomme", "category": "Fruits et légumes", "calories": 95, "proteines": 0.5, "glucides": 25.1, "lipides": 0.3},
    "pommes": {"name": "Pomme", "category": "Fruits et légumes", "calories": 95, "proteines": 0.5, "glucides": 25.1, "lipides": 0.3},
    "oeuf": {"name": "Œuf", "category": "Autre", "calories": 72, "proteines": 6.3, "glucides": 0.4, "lipides": 4.8},
    "oeufs": {"name": "Œuf", "category": "Autre", "calories": 72, "proteines": 6.3, "glucides": 0.4, "lipides": 4.8},
    "riz": {"name": "Riz cuit", "category": "Céréales et grains", "calories": 205, "proteines": 4.3, "glucides": 44.5, "lipides": 0.4},
    "pates": {"name": "Pâtes cuites", "category": "Céréales et grains", "calories": 220, "proteines": 8.1, "glucides": 43.2, "lipides": 1.3},
    "pâtes": {"name": "Pâtes cuites", "category": "Céréales et grains", "calories": 220, "proteines": 8.1, "glucides": 43.2, "lipides": 1.3},
    "poulet": {"name": "Poulet cuit", "category": "Viandes et poissons", "calories": 239, "proteines": 27.3, "glucides": 0.0, "lipides": 13.6},
    "banane": {"name": "Banane", "category": "Fruits et légumes", "calories": 105, "proteines": 1.3, "glucides": 27.0, "lipides": 0.4},
    "tomate": {"name": "Tomate", "category": "Fruits et légumes", "calories": 22, "proteines": 1.1, "glucides": 4.8, "lipides": 0.2},
    "pain": {"name": "Pain", "category": "Céréales et grains", "calories": 79, "proteines": 2.7, "glucides": 14.7, "lipides": 1.0},
    "fromage": {"name": "Fromage", "category": "Produits laitiers", "calories": 113, "proteines": 7.0, "glucides": 0.4, "lipides": 9.3},
}

def get_local_food_nutrition(query: str):
    key = normalize_name(query)
    if key in LOCAL_NUTRITION:
        return LOCAL_NUTRITION[key].copy()
    for alias, food in LOCAL_NUTRITION.items():
        if alias in key or key in alias:
            return food.copy()
    return None


def get_openfoodfacts_nutrition(query: str):
    """Recherche un produit dans Open Food Facts quand les données locales/USDA ne suffisent pas."""
    if not query:
        return None

    try:
        data = fetch_json(
            "https://world.openfoodfacts.org/api/v2/search",
            params={
                "search_terms": query,
                "page_size": 1,
                "fields": "product_name,nutriments,categories_tags",
            },
            timeout=8,
        )
    except Exception:
        return None

    products = data.get("products") or []
    if not products:
        return None

    product = products[0]
    nutriments = product.get("nutriments") or {}

    def number(*keys):
        for key in keys:
            value = nutriments.get(key)
            try:
                if value is not None and value != "":
                    return float(value)
            except (TypeError, ValueError):
                pass
        return 0.0

    name = product.get("product_name") or query
    categories = " ".join(product.get("categories_tags") or [])

    return {
        "name": name,
        "category": _normalize_category(categories),
        "calories": number(
            "energy-kcal_100g",
            "energy-kcal_value",
        ),
        "proteines": number("proteins_100g"),
        "glucides": number("carbohydrates_100g"),
        "lipides": number("fat_100g"),
    }


def get_generic_food_nutrition(query: str):
    """
    Dernier secours : fournit une estimation générique pour qu'un nouveau
    produit ne reste jamais sans affichage nutritionnel.
    Les valeurs sont des estimations pour 100 g, pas des valeurs exactes.
    """
    key = normalize_name(query)

    # Estimations génériques par grande famille.
    if any(word in key for word in [
        "lait", "yaourt", "yogourt", "fromage", "beurre", "creme"
    ]):
        return {
            "name": query,
            "category": "Produits laitiers",
            "calories": 150,
            "proteines": 5,
            "glucides": 12,
            "lipides": 8,
            "estimated": True,
        }

    if any(word in key for word in [
        "poulet", "boeuf", "bœuf", "porc", "jambon",
        "dinde", "viande", "poisson", "saumon", "thon"
    ]):
        return {
            "name": query,
            "category": "Viandes et poissons",
            "calories": 200,
            "proteines": 25,
            "glucides": 0,
            "lipides": 10,
            "estimated": True,
        }

    if any(word in key for word in [
        "pomme", "banane", "orange", "poire", "fraise",
        "fruit", "tomate", "carotte", "salade", "legume",
        "légume", "courgette", "brocoli"
    ]):
        return {
            "name": query,
            "category": "Fruits et légumes",
            "calories": 60,
            "proteines": 1,
            "glucides": 13,
            "lipides": 0.3,
            "estimated": True,
        }

    if any(word in key for word in [
        "riz", "pate", "pâtes", "pain", "farine", "cereale",
        "céréale", "avoine", "semoule"
    ]):
        return {
            "name": query,
            "category": "Céréales et grains",
            "calories": 200,
            "proteines": 6,
            "glucides": 40,
            "lipides": 2,
            "estimated": True,
        }

    # Produit totalement inconnu : estimation neutre.
    return {
        "name": query,
        "category": "Autre",
        "calories": 150,
        "proteines": 5,
        "glucides": 20,
        "lipides": 5,
        "estimated": True,
    }

def get_food_nutrition(query: str):
    # 1. Base locale : rapide et fiable pour les aliments courants.
    local = get_local_food_nutrition(query)
    if local:
        return local

    # 2. USDA si une clé API est configurée.
    foods = get_usda_foods(query, limit=1)
    if foods:
        return foods[0]

    # 3. Open Food Facts : fonctionne sans clé API pour beaucoup de produits.
    off = get_openfoodfacts_nutrition(query)
    if off:
        return off

    # 4. Dernier secours : estimation locale pour ne jamais laisser
    #    la carte "Données indisponibles".
    return get_generic_food_nutrition(query)

def get_themealdb_recipes(ingredient: str, limit: int = 3):
    if not ingredient:
        return []

    ingredient_terms = [term.strip() for term in ingredient.replace(";", ",").split(",") if term.strip()]
    if not ingredient_terms:
        return []

    result = []
    seen = set()

    for term in ingredient_terms:
        try:
            filtered = fetch_json(
                "https://www.themealdb.com/api/json/v1/1/filter.php",
                params={"i": term},
            )
        except Exception:
            continue

        meals = filtered.get("meals") or []
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
            recipe_name = d.get("strMeal", meal.get("strMeal", "Recette"))
            normalized_name = normalize_name(recipe_name)
            if not normalized_name or normalized_name in seen:
                continue

            description = (d.get("strInstructions") or "Aucune description disponible.").strip()
            if not description:
                description = "Aucune description disponible."

            result.append(
                {
                    "name": recipe_name,
                    "time": _estimate_recipe_time(d),
                    "difficulty": "Facile",
                    "description": description,
                }
            )
            seen.add(normalized_name)
            if len(result) >= limit:
                return result

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
