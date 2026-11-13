"""Limite les tentatives de connexion pour freiner les attaques par force brute."""
import os
import time
from threading import Lock

from fastapi import Request

MAX_FAILURES = 5          # échecs autorisés…
WINDOW_SECONDS = 15 * 60  # …par fenêtre de 15 minutes
MAX_TRACKED = 10_000      # plafond mémoire

_failures: dict[str, list[float]] = {}
_lock = Lock()


def client_ip(request: Request) -> str:
    """Adresse du client. X-Forwarded-For peut être falsifié : il n'est lu que derrière
    un proxy déclaré (TRUST_PROXY=1, par exemple sur Scalingo), en prenant la valeur
    ajoutée par le proxy (la dernière)."""
    direct = request.client.host if request.client else "inconnu"
    if os.getenv("TRUST_PROXY") != "1":
        return direct
    chain = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
    return chain[-1] if chain else direct


def _keys(request: Request, email: str) -> list[str]:
    # Deux compteurs : par adresse IP (un attaquant qui essaie plusieurs comptes)
    # et par compte (un attaquant qui change d'adresse).
    return [f"ip:{client_ip(request)}", f"email:{email}"]


def _recent(key: str, now: float) -> list[float]:
    return [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]


def retry_after(request: Request, email: str) -> int:
    """Secondes à attendre si la limite est atteinte, sinon 0."""
    now = time.monotonic()
    with _lock:
        waits = []
        for key in _keys(request, email):
            recent = _recent(key, now)
            if len(recent) >= MAX_FAILURES:
                waits.append(int(WINDOW_SECONDS - (now - recent[0])) + 1)
        return max(waits, default=0)


def record_failure(request: Request, email: str) -> None:
    now = time.monotonic()
    with _lock:
        for key in _keys(request, email):
            if key not in _failures and len(_failures) >= MAX_TRACKED:
                _failures.pop(next(iter(_failures)))
            _failures[key] = _recent(key, now) + [now]


def reset(request: Request, email: str) -> None:
    with _lock:
        _failures.pop(f"email:{email}", None)


def clear_all() -> None:
    with _lock:
        _failures.clear()
