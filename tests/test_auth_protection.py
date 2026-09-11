from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_login_page_is_public():
    response = client.get("/login")
    assert response.status_code == 200


def test_protected_pages_redirect_without_token():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers.get("location") == "/login"
