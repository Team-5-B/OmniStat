"""Task 4.4 tests: PATCH /api/account and POST /api/account/password."""
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.security import create_access_token, hash_password, verify_password

USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_ID = "33333333-3333-3333-3333-333333333333"
BUSINESS_ID = "22222222-2222-2222-2222-222222222222"


class FakeCursor:
    """pretends to be the users table."""

    def __init__(self, users):
        self.users = users
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        norm = " ".join(query.lower().split())
        if norm.startswith("update users set name"):
            name, email, user_id = params
            if email and any(u["email"] == email and uid != user_id for uid, u in self.users.items()):
                from psycopg.errors import UniqueViolation
                raise UniqueViolation("duplicate key")
            user = self.users.get(user_id)
            if user is None:
                self.row = None
                return
            user["name"] = name or user["name"]
            user["email"] = email or user["email"]
            self.row = (user["name"], user["email"])
        elif norm.startswith("select password_hash"):
            user = self.users.get(params[0])
            self.row = (user["hash"],) if user else None
        elif norm.startswith("update users set password_hash"):
            new_hash, user_id = params
            self.users[user_id]["hash"] = new_hash
            self.row = None
        else:
            raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, users):
        self.users = users

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.users)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "development-test-key-must-be-at-least-32-characters")
    users = {
        USER_ID: {"name": "Nick", "email": "nick@example.com", "hash": hash_password("oldpassword")},
        OTHER_ID: {"name": "Sam", "email": "sam@example.com", "hash": hash_password("whatever1")},
    }
    monkeypatch.setattr(main, "get_connection", lambda: FakeConnection(users))
    headers = {"Authorization": f"Bearer {create_access_token(USER_ID, BUSINESS_ID)}"}
    return TestClient(main.app), users, headers


def test_update_name_only_keeps_email(setup):
    http, users, headers = setup
    response = http.patch("/api/account", json={"name": "Nicholas"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"name": "Nicholas", "email": "nick@example.com"}


def test_update_email_is_lowercased(setup):
    http, users, headers = setup
    response = http.patch("/api/account", json={"email": "NEW@Example.com"}, headers=headers)
    assert response.status_code == 200, response.text
    assert users[USER_ID]["email"] == "new@example.com"


def test_update_email_taken_by_someone_else(setup):
    http, users, headers = setup
    response = http.patch("/api/account", json={"email": "sam@example.com"}, headers=headers)
    assert response.status_code == 409
    assert users[USER_ID]["email"] == "nick@example.com"


def test_update_rejects_empty_body_and_no_token(setup):
    http, users, headers = setup
    assert http.patch("/api/account", json={}, headers=headers).status_code == 422
    assert http.patch("/api/account", json={"name": "   "}, headers=headers).status_code == 422
    assert http.patch("/api/account", json={"name": "X"}).status_code == 401


def test_change_password_success(setup):
    http, users, headers = setup
    response = http.post(
        "/api/account/password",
        json={"current_password": "oldpassword", "new_password": "newpassword"},
        headers=headers,
    )
    assert response.status_code == 204, response.text
    assert verify_password("newpassword", users[USER_ID]["hash"])
    assert users[USER_ID]["hash"].startswith("$2b$")  # still a bcrypt hash, never plain text


def test_change_password_wrong_current_or_short_new(setup):
    http, users, headers = setup
    old_hash = users[USER_ID]["hash"]
    wrong = http.post(
        "/api/account/password",
        json={"current_password": "notmypassword", "new_password": "newpassword"},
        headers=headers,
    )
    assert wrong.status_code == 400
    short = http.post(
        "/api/account/password",
        json={"current_password": "oldpassword", "new_password": "short"},
        headers=headers,
    )
    assert short.status_code == 422
    assert users[USER_ID]["hash"] == old_hash  # nothing changed