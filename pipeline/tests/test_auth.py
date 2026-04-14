"""Unit tests for API key authentication."""

from __future__ import annotations

import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from coffee_pipeline.api.auth import verify_api_key

TEST_API_KEY = "test-secret-key-12345"


@pytest.fixture()
def app():
    """Minimal FastAPI app wired with the auth dependency."""
    _app = FastAPI(dependencies=[Depends(verify_api_key)])

    @_app.get("/items")
    async def list_items():
        return {"items": []}

    @_app.post("/items")
    async def create_item():
        return {"created": True}

    @_app.put("/items/{item_id}")
    async def update_item(item_id: str):
        return {"updated": item_id}

    @_app.delete("/items/{item_id}")
    async def delete_item(item_id: str):
        return {"deleted": item_id}

    return _app


@pytest.fixture()
def client(app, monkeypatch):
    monkeypatch.setenv("WEBAPP_API_KEY", TEST_API_KEY)
    return TestClient(app)


# --- GET requests pass without auth ---


def test_get_no_auth_required(client):
    resp = client.get("/items")
    assert resp.status_code == 200


# --- Missing Authorization header ---


def test_post_missing_header_returns_401(client):
    resp = client.post("/items")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing API key"


def test_put_missing_header_returns_401(client):
    resp = client.put("/items/abc")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing API key"


def test_delete_missing_header_returns_401(client):
    resp = client.delete("/items/abc")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing API key"


# --- Invalid Bearer format ---


def test_invalid_format_no_bearer_prefix(client):
    resp = client.post("/items", headers={"Authorization": f"Basic {TEST_API_KEY}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Authorization header format"


def test_invalid_format_bare_token(client):
    resp = client.post("/items", headers={"Authorization": TEST_API_KEY})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Authorization header format"


# --- Wrong API key ---


def test_wrong_api_key_returns_401(client):
    resp = client.post("/items", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


# --- Valid API key ---


def test_post_with_valid_key_succeeds(client):
    resp = client.post("/items", headers={"Authorization": f"Bearer {TEST_API_KEY}"})
    assert resp.status_code == 200
    assert resp.json()["created"] is True


def test_put_with_valid_key_succeeds(client):
    resp = client.put("/items/abc", headers={"Authorization": f"Bearer {TEST_API_KEY}"})
    assert resp.status_code == 200


def test_delete_with_valid_key_succeeds(client):
    resp = client.delete("/items/abc", headers={"Authorization": f"Bearer {TEST_API_KEY}"})
    assert resp.status_code == 200


# --- Edge: WEBAPP_API_KEY not set ---


def test_unset_env_rejects_any_key(monkeypatch, app):
    monkeypatch.delenv("WEBAPP_API_KEY", raising=False)
    c = TestClient(app)
    resp = c.post("/items", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"
