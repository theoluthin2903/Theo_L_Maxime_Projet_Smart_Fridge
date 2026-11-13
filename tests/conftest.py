"""Configuration des tests : base SQLite temporaire et clé JWT de test.
Le fichier .env n'est jamais utilisé (les variables sont définies avant l'import de l'application)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["JWT_SECRET_KEY"] = "cle-de-test-uniquement-pour-pytest-0123456789"
os.environ.pop("TRUST_PROXY", None)
os.environ.pop("COOKIE_SECURE", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.core import rate_limit  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_limits():
    rate_limit.clear_all()
    yield
    rate_limit.clear_all()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
