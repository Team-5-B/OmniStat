import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock
from backend import security
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def test_owner_allowed(monkeypatch):
    fake_conn = MagicMock()

    fake_cursor = (
        fake_conn.__enter__.return_value
        .cursor.return_value.__enter__.return_value
    )

    fake_cursor.fetchone.return_value = ("owner",)

    monkeypatch.setattr(
        security, "get_connection", lambda: fake_conn
    )

    claims = {
        "sub": "user123",
        "business_id": "business123"
    }

    result = security.require_owner(claims)

    assert result == claims

def test_employee_blocked(monkeypatch):
    fake_conn = MagicMock()

    fake_cursor = (
        fake_conn.__enter__.return_value
        .cursor.return_value.__enter__.return_value
    )

    fake_cursor.fetchone.return_value = ("employee",)

    monkeypatch.setattr(
        security, "get_connection", lambda: fake_conn
    )

    claims = {
        "sub": "user123",
        "business_id": "business123"
    }

    with pytest.raises(HTTPException) as error:
        security.require_owner(claims)

    assert error.value.status_code == 403
def test_no_membership(monkeypatch):
    fake_conn = MagicMock()

    fake_cursor = (
        fake_conn.__enter__.return_value
        .cursor.return_value.__enter__.return_value
    )

    fake_cursor.fetchone.return_value = None

    monkeypatch.setattr(
        security, "get_connection", lambda: fake_conn
    )

    claims = {
        "sub": "user123",
        "business_id": "business123"
    }

    with pytest.raises(HTTPException) as error:
        security.require_owner(claims)

    assert error.value.status_code == 403

def test_owner_requires_login():
    app = FastAPI()

    @app.get("/test-owner")
    def owner_route(
        claims: dict = Depends(security.require_owner)
    ):
        return {"message": "Access granted"}

    client = TestClient(app)

    response = client.get("/test-owner")

    assert response.status_code == 401