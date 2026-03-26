from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="learnsite-tests-"))
_DB_PATH = _TEST_ROOT / "learnsite-test.db"
_RESOURCE_DIR = _TEST_ROOT / "resources"
_BACKUP_DIR = _TEST_ROOT / "backups"
_BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ["LEARNSITE_SQLITE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["LEARNSITE_RESOURCE_STORAGE_DIR"] = _RESOURCE_DIR.as_posix()
os.environ["LEARNSITE_BACKUP_STORAGE_DIR"] = _BACKUP_DIR.as_posix()
os.environ["LEARNSITE_CORS_ORIGINS"] = '["http://127.0.0.1:4174","http://localhost:4174"]'

from app.main import app
from app.core.auth import SESSION_STORE
from app.core.database import SessionLocal, engine


def _reset_test_storage() -> None:
    engine.dispose()
    SESSION_STORE.clear()
    if _DB_PATH.exists():
        _DB_PATH.unlink()
    for directory in (_RESOURCE_DIR, _BACKUP_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def client():
    _reset_test_storage()
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    SESSION_STORE.clear()


@pytest.fixture
def db_session(client):
    with SessionLocal() as session:
        yield session


@pytest.fixture
def login(client):
    def _login(*, role: str, school_code: str, username: str, password: str) -> tuple[dict[str, str], dict]:
        response = client.post(
            "/api/auth/login",
            json={
                "role": role,
                "school_code": school_code,
                "username": username,
                "password": password,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        return {"Authorization": f"Bearer {payload['session']['token']}"}, payload

    return _login


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)
