"""Pipeline asynchrone multi-API : calcule les apports nutritionnels réels
d'une recette TheMealDB en interrogeant l'USDA pour chaque ingrédient, en
parallèle, avec asyncio.gather (voir le brief, partie B).

Ce module est indépendant de app/web/data.py pour ne rien casser dans
l'existant : il réutilise `flatten_meal_ingredients` et `IngredientQuantity`
mais n'ajoute que de nouvelles fonctions.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

import httpx
from pydantic import BaseModel, model_validator
from dotenv import load_dotenv

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# ---------------------------------------------------------------------------
# Piège n°4 du brief : décalage lexical anglais britannique (TheMealDB) vs
# nomenclature américaine (USDA FoodData Central). On tente d'abord le nom
# tel quel, puis ce mapping comme repli si l'USDA ne renvoie rien.
# ---------------------------------------------------------------------------
UK_TO_US_INGREDIENT_MAP: dict[str, str] = {
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "coriander": "cilantro",
    "fresh coriander": "fresh cilantro",
    "spring onion": "scallion",
    "spring onions": "scallions",
    "plain flour": "all purpose flour",
    "self-raising flour": "self rising flour",
    "self raising flour": "self rising flour",
    "icing sugar": "powdered sugar",
    "caster sugar": "granulated sugar",
    "double cream": "heavy cream",
    "single cream": "light cream",
    "minced beef": "ground beef",
    "beef mince": "ground beef",
    "prawns": "shrimp",
    "king prawns": "jumbo shrimp",
    "rocket": "arugula",
    "swede": "rutabaga",
    "chips": "french fries",
    "biscuits": "cookies",
    "tomato puree": "tomato paste",
    "cornflour": "cornstarch",
    "black treacle": "molasses",
    "bicarbonate of soda": "baking soda",
    "streaky bacon": "bacon",
    "back bacon": "canadian bacon",
    "chestnut mushrooms": "cremini mushrooms",
    "clingfilm": "plastic wrap",  # non alimentaire mais bien vu dans certaines recettes
    "maize": "corn",
    "haricot beans": "navy beans",
    "runner beans": "green beans",
}


class UsdaLookupError(Exception):
    """Erreur volontairement distincte pour les pannes réseau/API USDA."""

    def __init__(self, message: str, *, is_rate_limited: bool = False, is_timeout: bool = False):
        super().__init__(message)
        self.is_rate_limited = is_rate_limited
        self.is_timeout = is_timeout


async def _usda_search_async(client: httpx.AsyncClient, term: str, *, retries: int = 2) -> dict:
    """Interroge l'USDA de façon asynchrone.

    Gère explicitement :
    - les timeouts (httpx.TimeoutException) ;
    - le code 429 "Too Many Requests", avec un petit backoff exponentiel
      avant de réessayer, comme demandé dans le brief (partie D) ;
    - toute autre erreur HTTP, remontée sans faire planter le pipeline.
    """
    if not USDA_API_KEY:
        raise UsdaLookupError("USDA_API_KEY manquante")

    params = {
        "query": term,
        "dataType": ["SR Legacy", "Foundation"],
        "pageSize": 5,
        "api_key": USDA_API_KEY,
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(USDA_SEARCH_URL, params=params, timeout=8)
            if response.status_code == 429:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                raise UsdaLookupError(f"USDA a limité les requêtes pour « {term} »", is_rate_limited=True)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.3 * (2 ** attempt))
                continue
            raise UsdaLookupError(f"Timeout USDA pour « {term} »", is_timeout=True) from exc
        except httpx.HTTPStatusError as exc:
            raise UsdaLookupError(f"Erreur USDA {exc.response.status_code} pour « {term} »") from exc
        except httpx.RequestError as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.3 * (2 ** attempt))
                continue
            raise UsdaLookupError(f"USDA injoignable pour « {term} »") from exc

    raise UsdaLookupError(f"Échec USDA pour « {term} »") from last_error


def _extract_usda_energy_kcal(nutrients: list[dict]) -> float:
    kcal_by_id: dict[int, float] = {}
    kj_value: float | None = None
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
            kj_value = n["value"]
    for nutrient_id in (1008, 2047, 2048):
        if nutrient_id in kcal_by_id:
            return kcal_by_id[nutrient_id]
    if kcal_by_id:
        return next(iter(kcal_by_id.values()))
    return round(kj_value / 4.184, 1) if kj_value is not None else 0.0


def _extract_usda_nutrient(nutrients: list[dict], nutrient_id: int) -> float:
    for item in nutrients:
        if isinstance(item, dict) and int(item.get("nutrientId", -1) or -1) == nutrient_id:
            return float(item.get("value") or 0)
    return 0.0


async def get_ingredient_nutrition_per_100g_async(client: httpx.AsyncClient, ingredient_name: str) -> Optional[dict]:
    """Renvoie les valeurs USDA pour 100 g d'un ingrédient, ou None si introuvable.

    Essaie d'abord le nom tel quel (TheMealDB), puis le mapping UK -> US en
    repli si l'USDA ne renvoie rien (piège n°4 du brief).
    """
    tried = [ingredient_name]
    mapped = UK_TO_US_INGREDIENT_MAP.get(ingredient_name.strip().lower())
    if mapped:
        tried.append(mapped)

    last_error: UsdaLookupError | None = None
    for term in tried:
        try:
            data = await _usda_search_async(client, term)
        except UsdaLookupError as exc:
            last_error = exc
            continue

        foods = data.get("foods") or []
        if not foods:
            continue

        nutrients = foods[0].get("foodNutrients", [])
        return {
            "matched_name": foods[0].get("description", term),
            "used_uk_us_mapping": term != ingredient_name,
            "calories": _extract_usda_energy_kcal(nutrients),
            "proteines": _extract_usda_nutrient(nutrients, 1003),
            "glucides": _extract_usda_nutrient(nutrients, 1005),
            "lipides": _extract_usda_nutrient(nutrients, 1004),
        }

    if last_error is not None:
        # On ne fait pas planter le pipeline : l'ingrédient sera simplement
        # marqué "estimé" côté appelant.
        print(f"[nutrition_engine] {last_error}")
    return None


_FRACTIONS = {"¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

# Conversions volume -> grammes très approximatives (densité proche de l'eau).
# But pédagogique : donner un ordre de grandeur, pas une valeur exacte.
_UNIT_TO_GRAMS = {
    "g": 1, "gram": 1, "grams": 1,
    "kg": 1000, "kilogram": 1000, "kilograms": 1000,
    "ml": 1, "milliliter": 1, "milliliters": 1, "millilitre": 1,
    "l": 1000, "liter": 1000, "litre": 1000,
    "tsp": 5, "teaspoon": 5, "teaspoons": 5,
    "tbsp": 15, "tablespoon": 15, "tablespoons": 15,
    "cup": 240, "cups": 240,
    "oz": 28.35, "ounce": 28.35, "ounces": 28.35,
    "lb": 453.6, "pound": 453.6, "pounds": 453.6,
    "pinch": 0.5,
}
_VOLUME_UNITS = {"tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon", "tablespoons", "cup", "cups"}

# Densité approximative (g pour 1 "cup") de quelques ingrédients secs
# fréquents, très différente de l'eau (~240 g/cup) utilisée par défaut :
# une tasse de farine ne pèse pas la même chose qu'une tasse de lait.
# Approximation volontairement simple, à but pédagogique.
_DRY_DENSITY_G_PER_CUP = {
    "flour": 125, "self rising flour": 130, "self-raising flour": 130,
    "plain flour": 125, "all purpose flour": 125, "wholemeal flour": 120,
    "cornflour": 120, "cornstarch": 120,
    "sugar": 200, "granulated sugar": 200, "caster sugar": 200,
    "icing sugar": 120, "powdered sugar": 120, "brown sugar": 220,
    "breadcrumbs": 100, "bread crumbs": 100,
    "butter": 227, "margarine": 227,
    "rice": 185, "oats": 90, "cocoa powder": 90,
    "baking powder": 192, "baking soda": 220,
}


def _cup_grams_for(ingredient_name: str) -> float:
    text = (ingredient_name or "").strip().lower()
    for keyword, grams in _DRY_DENSITY_G_PER_CUP.items():
        if keyword in text:
            return grams
    return _UNIT_TO_GRAMS["cup"]  # densité par défaut (proche de l'eau)


_DEFAULT_PORTION_GRAMS = 100  # utilisé quand la mesure ne peut vraiment pas être interprétée

# Formulations culinaires sans chiffre ("Pinch of salt", "To taste"...) : avant
# ce correctif, elles retombaient toutes sur 100 g par défaut, ce qui
# surestimait énormément les épices (une pincée pèse <1 g, pas 100 g).
_TEXTUAL_SMALL_AMOUNTS = {
    "pinch": 0.3,
    "dash": 0.3,
    "sprinkle": 0.5,
    "splash": 5,
    "to taste": 1,
    "as needed": 1,
    "a little": 2,
    "a few": 5,
    "few": 5,
    "some": 5,
    "handful": 30,
}


def parse_quantity_grams(measure: str, ingredient_name: str = "") -> tuple[float, bool]:
    """Convertit une mesure TheMealDB ("2 tbsp", "1/2 cup", "3") en grammes.

    Renvoie (grammes, estimé). estimé=True signifie qu'on est retombé sur une
    portion par défaut faute de pouvoir interpréter le texte (ex: "quelques",
    "1 tin", unité inconnue...).
    """
    text = (measure or "").strip().lower()
    if not text:
        return _DEFAULT_PORTION_GRAMS, True

    for symbol, value in _FRACTIONS.items():
        text = text.replace(symbol, f" {value} ")

    match = re.match(r"\s*(\d+\s*/\s*\d+|\d+(?:[.,]\d+)?)", text)
    if not match:
        # Pas de chiffre du tout : on cherche une formulation reconnue
        # ("pinch", "to taste"...) avant de retomber sur la portion par
        # défaut, plus large et réservée aux cas vraiment ambigus.
        for phrase, grams in _TEXTUAL_SMALL_AMOUNTS.items():
            if phrase in text:
                return grams, True
        return _DEFAULT_PORTION_GRAMS, True

    raw_number = match.group(1).replace(",", ".")
    try:
        if "/" in raw_number:
            num, den = raw_number.split("/")
            quantity = float(num) / float(den)
        else:
            quantity = float(raw_number)
    except (ValueError, ZeroDivisionError):
        return _DEFAULT_PORTION_GRAMS, True

    rest = text[match.end():].strip()
    # Extrait le premier "mot" de l'unité (ex: "lb ground beef" -> "lb") et
    # compare une correspondance EXACTE, jamais un simple préfixe : sinon
    # "lb" (livre) matchait par erreur "l" (litre) car "lb".startswith("l"),
    # ce qui multipliait par ~2,2 la quantité réelle sans jamais être marqué
    # comme une estimation.
    first_word_match = re.match(r"[a-zà-ÿ]+", rest)
    unit_token = first_word_match.group(0) if first_word_match else ""
    if unit_token in ("cup", "cups"):
        return quantity * _cup_grams_for(ingredient_name), False
    grams_per_unit = _UNIT_TO_GRAMS.get(unit_token)
    if grams_per_unit is not None:
        return quantity * grams_per_unit, False

    # Un nombre seul sans unité reconnue (ex: "2 eggs") : on estime une
    # portion moyenne de 50 g par unité, marquée comme estimation.
    return quantity * 50, True


class RecipeIngredients(BaseModel):
    """Modèle Pydantic qui aplatit lui-même la structure éclatée de
    TheMealDB (strIngredient1..20 / strMeasure1..20) via un validateur
    personnalisé, comme demandé dans le brief (piège n°1)."""

    items: list[dict] = []

    @model_validator(mode="before")
    @classmethod
    def _flatten_raw_meal(cls, data):
        if isinstance(data, dict) and "items" not in data:
            raw_meal = data
            items, seen = [], set()
            for index in range(1, 21):
                name = (raw_meal.get(f"strIngredient{index}") or "").strip()
                if not name:
                    continue
                key = name.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "ingredient": name,
                    "measure": (raw_meal.get(f"strMeasure{index}") or "").strip(),
                })
            return {"items": items}
        return data


async def compute_recipe_nutrition_async(client: httpx.AsyncClient, meal: dict) -> dict:
    """Calcule les apports réels (calories/macros) d'une recette TheMealDB en
    interrogeant l'USDA pour chaque ingrédient EN PARALLÈLE (asyncio.gather).
    """
    ingredients = RecipeIngredients.model_validate(meal).items
    if not ingredients:
        return {"calories": 0, "proteines": 0, "glucides": 0, "lipides": 0, "estimated": True, "missing": []}

    # Une requête USDA par ingrédient, toutes lancées ensemble.
    lookups = await asyncio.gather(
        *[get_ingredient_nutrition_per_100g_async(client, item["ingredient"]) for item in ingredients]
    )

    total = {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}
    missing: list[str] = []
    any_estimated = False

    for item, nutrition in zip(ingredients, lookups):
        grams, portion_estimated = parse_quantity_grams(item["measure"], item["ingredient"])
        if portion_estimated:
            any_estimated = True

        if nutrition is None:
            missing.append(item["ingredient"])
            any_estimated = True
            continue

        factor = grams / 100
        total["calories"] += nutrition["calories"] * factor
        total["proteines"] += nutrition["proteines"] * factor
        total["glucides"] += nutrition["glucides"] * factor
        total["lipides"] += nutrition["lipides"] * factor

    return {
        "calories": round(total["calories"]),
        "proteines": round(total["proteines"]),
        "glucides": round(total["glucides"]),
        "lipides": round(total["lipides"]),
        "estimated": any_estimated or bool(missing),
        "missing": missing,
    }


async def compute_nutrition_for_recipes_async(meals: list[dict]) -> list[dict]:
    """Calcule la nutrition réelle de plusieurs recettes en parallèle
    (une session httpx partagée, un gather par recette et un gather global).
    """
    if not meals:
        return []

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[compute_recipe_nutrition_async(client, meal) for meal in meals]
        )
    return list(results)