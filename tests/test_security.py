"""Tests de sécurité : `python -m pytest`"""
import os
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "Frigo2026!"


def new_email():
    return f"test-{uuid.uuid4().hex[:8]}@example.test"


def register(client, email, password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email, password=PASSWORD, **headers):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers)


# ─── Inscription ────────────────────────────────────────────────────────────

def test_inscription_refuse_un_mot_de_passe_faible(client):
    assert register(client, new_email(), "abc").status_code == 422
    assert register(client, new_email(), "seulementdeslettres").status_code == 422
    assert register(client, new_email(), PASSWORD).status_code == 200


def test_inscription_refuse_une_adresse_piegee(client):
    # Une « adresse » contenant du HTML ne doit jamais être enregistrée.
    assert register(client, "<img src=x onerror=alert(1)>@x.fr", PASSWORD).status_code == 422
    assert register(client, "pas-une-adresse", PASSWORD).status_code == 422


def test_adresse_normalisee_en_minuscules(client):
    email = new_email()
    assert register(client, email.upper(), PASSWORD).status_code == 200
    assert register(client, email, PASSWORD).status_code == 400  # même compte
    assert login(client, email).status_code == 200


# ─── Connexion ──────────────────────────────────────────────────────────────

def test_meme_message_que_le_compte_existe_ou_non(client):
    email = new_email()
    register(client, email)
    wrong = login(client, email, "MauvaisMdp1")
    unknown = login(client, new_email(), "MauvaisMdp1")
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_blocage_apres_cinq_echecs(client):
    email = new_email()
    register(client, email)
    for _ in range(5):
        assert login(client, email, "MauvaisMdp1").status_code == 400
    blocked = login(client, email)  # même avec le bon mot de passe
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_x_forwarded_for_falsifie_ne_contourne_pas_le_blocage(client):
    email = new_email()
    register(client, email)
    for i in range(5):
        login(client, email, "MauvaisMdp1", **{"X-Forwarded-For": f"203.0.113.{i}"})
    assert login(client, email, **{"X-Forwarded-For": "198.51.100.9"}).status_code == 429


def test_cookie_httponly_et_secure_derriere_https(client):
    email = new_email()
    register(client, email)
    plain = login(client, email).headers["set-cookie"].lower()
    assert "httponly" in plain and "samesite=lax" in plain and "secure" not in plain
    secure = login(client, email, **{"X-Forwarded-Proto": "https"}).headers["set-cookie"].lower()
    assert "; secure" in secure


def test_le_jeton_n_est_pas_copie_dans_le_navigateur(client):
    html = client.get("/login").text
    assert ".setItem('smartfridge_token'" not in html


# ─── XSS ────────────────────────────────────────────────────────────────────

def test_nom_de_produit_piege_echappe_dans_les_alertes(client):
    email = new_email()
    register(client, email)
    assert login(client, email).status_code == 200
    payload = "<script>alert(1)</script>"
    soon = (date.today() + timedelta(days=1)).isoformat()
    client.post("/fridge", data={"name": payload, "quantity": 1, "expiration_date": soon, "category": "", "notes": ""})
    html = client.get("/alerts").text
    assert payload not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_parametres_de_l_accueil_jamais_reinjectes_tels_quels(client):
    email = new_email()
    register(client, email)
    assert login(client, email).status_code == 200
    html = client.get("/", params={
        "next_day": "1",
        "new_date": "<script>alert(1)</script>",
        "expired": "<img src=x onerror=alert(2)>",
    }).text
    assert "<script>alert(1)</script>" not in html
    assert "onerror=alert(2)" not in html
    ok = client.get("/", params={"next_day": "1", "new_date": "2026-01-02", "expired": "3"}).text
    assert "02/01/2026" in ok and "3 produit(s)" in ok


# ─── Isolation des utilisateurs ─────────────────────────────────────────────

def test_un_visiteur_ne_voit_pas_le_frigo_du_dernier_utilisateur(client):
    email = new_email()
    register(client, email)
    assert login(client, email).status_code == 200
    secret = f"produit-prive-{uuid.uuid4().hex[:6]}"
    soon = (date.today() + timedelta(days=1)).isoformat()
    client.post("/fridge", data={"name": secret, "quantity": 1, "expiration_date": soon, "category": "", "notes": ""})
    assert secret in client.get("/alerts").text

    client.cookies.clear()  # même serveur, mais visiteur non connecté
    assert secret not in client.get("/alerts").text


# ─── Configuration ──────────────────────────────────────────────────────────

def test_en_tetes_de_securite(client):
    r = client.get("/login")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "strict-origin" in r.headers["referrer-policy"]
    assert "strict-transport-security" not in r.headers
    https = client.get("/login", headers={"X-Forwarded-Proto": "https"})
    assert "max-age" in https.headers["strict-transport-security"]


def test_refus_de_demarrer_sans_cle_jwt_solide():
    env = {**os.environ, "JWT_SECRET_KEY": "trop-courte"}
    result = subprocess.run([sys.executable, "-c", "import app.core.jwt"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr
