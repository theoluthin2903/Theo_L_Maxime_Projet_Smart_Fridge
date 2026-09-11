import main


def test_fridge_starts_empty():
    assert main.fridge_items == []


def test_search_requires_query_for_usda_and_themealdb():
    assert main.get_usda_foods("", limit=1) == []
    assert main.get_themealdb_recipes("", limit=1) == []
