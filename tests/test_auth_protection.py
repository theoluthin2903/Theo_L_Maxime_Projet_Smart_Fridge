from uuid import uuid4

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}+{uuid4().hex[:8]}@example.com"


def test_login_page_is_public():
    response = client.get("/login")
    assert response.status_code == 200


def test_protected_pages_redirect_without_token():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers.get("location") == "/login"


def test_login_page_does_not_show_logout_button_without_auth():
    response = client.get("/login")
    assert response.status_code == 200
    assert "Se déconnecter" not in response.text


def test_register_does_not_set_auth_cookie():
    email = unique_email("register")
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    assert "set-cookie" not in response.headers


def test_login_sets_auth_cookie():
    email = unique_email("login")
    client.post(
        "/auth/register",
        json={"email": email, "password": "secret123"},
    )
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login.status_code == 200
    assert "set-cookie" in login.headers
    assert "access_token=" in login.headers["set-cookie"]

    protected = client.get("/", cookies={"access_token": login.json()["access_token"]})
    assert protected.status_code == 200


def test_password_must_be_at_least_6_characters():
    email = unique_email("shortpass")

    register = client.post(
        "/auth/register",
        json={"email": email, "password": "12345"},
    )
    assert register.status_code == 422

    client.post(
        "/auth/register",
        json={"email": unique_email("validpass"), "password": "secret123"},
    )

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "12345"},
    )
    assert login.status_code == 422


def test_auth_dark_theme_has_specific_css_rules():
    css = open("static/styles.css", encoding="utf-8").read()

    assert "html.dark .auth-shell" in css
    assert "html.dark .auth-card--green" in css
    assert "html.dark .auth-card--dark" in css


def test_theme_toggle_button_uses_the_correct_text_element():
    response = client.get("/login")
    assert response.status_code == 200
    html = response.text

    assert 'id="theme-toggle-text"' in html
    assert 'getElementById(\'theme-toggle-text\')' in html
    assert 'text.textContent' in html
    
