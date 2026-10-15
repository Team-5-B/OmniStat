"""Task 2.3 tests: GET /api/auth/me."""
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.security import create_access_token

USER_ID = "11111111-1111-1111-1111-111111111111"
BUSINESS_ID = "22222222-2222-2222-2222-222222222222"


class FakeCursor:
    """Pretends to be the database. Only knows about one user."""

    def __init__(self):
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        user_id, business_id = params
        if user_id == USER_ID and business_id == BUSINESS_ID:
            self.row = ("Nick", "nick@example.com", BUSINESS_ID, "Demo Shop", "owner")
        else:
            self.row = None  # User or membership doesn't exist.

    def fetchone(self):
        return self.row


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor()


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "development-test-key-must-be-at-least-32-characters")
    monkeypatch.setattr(main, "get_connection", lambda: FakeConnection())
    return TestClient(main.app)


def test_me_returns_user_and_business(http):
    token = create_access_token(USER_ID, BUSINESS_ID)
    response = http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Nick"
    assert body["business_name"] == "Demo Shop"
    assert body["role"] == "owner"


def test_me_rejects_missing_token(http):
    assert http.get("/api/auth/me").status_code == 401


def test_me_rejects_fake_token(http):
    response = http.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_rejects_token_for_deleted_user(http):
    token = create_access_token("99999999-9999-9999-9999-999999999999", BUSINESS_ID)
    response = http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401