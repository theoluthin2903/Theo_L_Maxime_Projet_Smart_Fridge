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



def get_available_products(query: str = "", limit: int = 200):
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
                "category": (category or "Autre").strip() or "Autre",
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

    for term in search_terms:
        term = (term or "").strip()
        if not term:
            continue

        for item in get_usda_foods(term, limit=12):
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


def get_available_product_names(query: str = "", limit: int = 200):
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
