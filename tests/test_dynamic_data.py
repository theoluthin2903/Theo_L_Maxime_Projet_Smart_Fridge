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
