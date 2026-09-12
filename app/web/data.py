import os

import requests

USDA_API_KEY = os.getenv("USDA_API_KEY")
fridge_items = []


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
        name = item.get("name", "")
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
