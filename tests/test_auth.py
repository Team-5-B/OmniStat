
from uuid import uuid4

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.security import create_access_token, hash_password, verify_access_token, verify_password

class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        norm = " ".join(query.lower().split())
        if norm.startswith("insert into businesses"):
            business_id = uuid4()
            self.state["businesses"].append({"id": business_id, "name": params[0]})
            self.row = (business_id,)
        elif norm.startswith("insert into users"):
            if any(u["email"] == params[1] for u in self.state["users"]):
                # The production PostgreSQL database raises UniqueViolation.
                # For this isolated test, use an HTTP conflict to simulate it.
                from psycopg.errors import UniqueViolation
                raise UniqueViolation("duplicate key")
            user_id = uuid4()
            self.state["users"].append({"id": user_id, "name": params[0], "email": params[1], "hash": params[2]})
            self.row = (user_id,)
        elif norm.startswith("insert into memberships"):
            self.state["memberships"].append({"user_id": params[0], "business_id": params[1], "role": params[2]})
            self.row = None
        elif norm.startswith("select u.id"):
            user = next((u for u in self.state["users"] if u["email"] == params[0]), None)
            membership = next((m for m in self.state["memberships"] if user and m["user_id"] == user["id"]), None)
            self.row = (user["id"], user["hash"], membership["business_id"]) if membership else None
        else:
            raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.before = None

    def __enter__(self):
        self.before = {key: rows.copy() for key, rows in self.state.items()}
        return self

    def __exit__(self, exception_type, *args):
        if exception_type:
            self.state.clear()
            self.state.update(self.before)  # Simulate transaction rollback.
        return False

    def cursor(self):
        return FakeCursor(self.state)


@pytest.fixture
def client(monkeypatch):
    state = {"businesses": [], "users": [], "memberships": []}
    monkeypatch.setenv("JWT_SECRET_KEY", "development-test-key-must-be-at-least-32-characters")
    monkeypatch.setattr(main, "get_connection", lambda: FakeConnection(state))
    return TestClient(main.app), state


def test_register_creates_all_three_rows_and_bcrypt_hash(client):
    http, state = client
    response = http.post("/api/auth/register", json={
        "name": "Junior", "business_name": "Demo Shop", "email": "JUNIOR@example.com", "password": "testpassword123"
    })
    assert response.status_code == 201, response.text
    assert len(state["businesses"]) == len(state["users"]) == len(state["memberships"]) == 1
    assert state["users"][0]["email"] == "junior@example.com"
    assert state["users"][0]["hash"] != "testpassword123"
    assert verify_password("testpassword123", state["users"][0]["hash"])
    assert verify_access_token(response.json()["access_token"])["sub"] == response.json()["user_id"]


def test_duplicate_email_rolls_back_new_business(client):
    http, state = client
    body = {"name": "Junior", "business_name": "Demo Shop", "email": "junior@example.com", "password": "testpassword123"}
    assert http.post("/api/auth/register", json=body).status_code == 201
    response = http.post("/api/auth/register", json={**body, "business_name": "Another Shop"})
    assert response.status_code == 409
    assert len(state["businesses"]) == 1
    assert len(state["users"]) == 1


def test_login_correct_and_wrong_password(client):
    http, _state = client
    http.post("/api/auth/register", json={"name": "Junior", "business_name": "Demo Shop", "email": "junior@example.com", "password": "testpassword123"})
    ok = http.post("/api/auth/login", json={"email": "junior@example.com", "password": "testpassword123"})
    bad = http.post("/api/auth/login", json={"email": "junior@example.com", "password": "wrongpassword"})
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    assert bad.status_code == 401


def test_missing_user_and_bad_input(client):
    http, _state = client
    assert http.post("/api/auth/login", json={"email": "absent@example.com", "password": "anything"}).status_code == 401
    assert http.post("/api/auth/register", json={"name": "A", "business_name": "B", "email": "bad-email", "password": "short"}).status_code == 422


def test_tampered_token_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "development-test-key-must-be-at-least-32-characters")
    token = create_access_token("user123", "business123")
    assert verify_access_token(token)["sub"] == "user123"
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        verify_access_token(token + "a")
    assert exc.value.status_code == 401
