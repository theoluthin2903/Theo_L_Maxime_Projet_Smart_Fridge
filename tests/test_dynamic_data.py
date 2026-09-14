import main


def test_fridge_starts_empty():
    assert main.fridge_items == []


def test_search_requires_query_for_usda_and_themealdb():
    assert main.get_usda_foods("", limit=1) == []
    assert main.get_themealdb_recipes("", limit=1) == []


def test_missing_api_key_does_not_return_hardcoded_values(monkeypatch):
    import app.web.data as data

    monkeypatch.setattr(data, "USDA_API_KEY", None)
    assert data.get_usda_foods("milk", limit=3) == []


def test_usda_raw_foods_are_filtered_and_uses_nutrient_ids(monkeypatch):
    import app.web.data as data

    def fake_fetch_json(url, params=None, timeout=15):
        assert params["dataType"] == ["SR Legacy", "Foundation"]
        return {
            "foods": [
                {
                    "description": "Eggplant",
                    "foodCategory": "Vegetables and Vegetable Products",
                    "foodNutrients": [
                        {"nutrientId": 1008, "nutrientName": "Energy", "value": 35},
                        {"nutrientId": 1003, "nutrientName": "Protein", "value": 1.2},
                        {"nutrientId": 1004, "nutrientName": "Total lipid (fat)", "value": 0.2},
                        {"nutrientId": 1005, "nutrientName": "Carbohydrate, by difference", "value": 6.6},
                    ],
                }
            ]
        }

    monkeypatch.setattr(data, "USDA_API_KEY", "demo-key")
    monkeypatch.setattr(data, "fetch_json", fake_fetch_json)

    results = data.get_usda_foods("eggplant", limit=1)

    assert results[0]["name"] == "Eggplant"
    assert results[0]["calories"] == 35
    assert results[0]["proteines"] == 1.2
    assert results[0]["glucides"] == 6.6
    assert results[0]["lipides"] == 0.2


def test_themealdb_ingredients_are_flattened_and_normalized():
    import app.web.data as data

    payload = {
        "strMeal": "Aubergine Grillée",
        "strInstructions": "Étape 1. Couper l'aubergine. Étape 2. Griller.",
        "strIngredient1": "Aubergine",
        "strMeasure1": "200 g",
        "strIngredient2": "Huile d'olive",
        "strMeasure2": "10 ml",
        "strIngredient3": "",
        "strMeasure3": "",
    }

    ingredients = data.flatten_meal_ingredients(payload)

    assert ingredients[0].ingredient == "Aubergine"
    assert ingredients[0].normalized == "aubergine"
    assert ingredients[1].ingredient == "Huile d'olive"
    assert len(ingredients) == 2


def test_french_users_have_separate_fridges():
    import app.web.data as data

    data.add_fridge_item("Lait", 1, 1, "2026-09-20", "Produits laitiers", "")
    data.add_fridge_item("Pommes", 2, 2, "2026-09-22", "Fruits", "")

    user_one = data.load_fridge_items(1)
    user_two = data.load_fridge_items(2)

    assert [item["name"] for item in user_one] == ["Lait"]
    assert [item["name"] for item in user_two] == ["Pommes"]

    data.delete_fridge_item(user_one[0]["id"], 1)
    data.delete_fridge_item(user_two[0]["id"], 2)
