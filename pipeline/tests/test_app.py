"""Unit tests for the FastAPI application (app.py).

Covers: lifespan manager initialisation, CORS headers, router mounting,
and the POST /api/auth/verify endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-app-key-99"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("WEBAPP_API_KEY", TEST_API_KEY)
    from coffee_pipeline.api.app import app

    with TestClient(app) as c:
        yield c


# --- Lifespan: managers attached to app.state ---


def test_managers_initialised(client):
    from coffee_pipeline.api.app import app

    assert hasattr(app.state, "job_manager")
    assert hasattr(app.state, "article_manager")
    assert hasattr(app.state, "git_manager")


# --- CORS preflight ---


def test_cors_preflight(client):
    resp = client.options(
        "/api/jobs",
        headers={
            "Origin": "http://localhost:4321",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:4321"


# --- Router mounting: jobs and articles reachable ---


def test_jobs_router_mounted(client):
    resp = client.get("/api/jobs")
    assert resp.status_code == 200


def test_articles_router_mounted(client):
    resp = client.get("/api/articles")
    assert resp.status_code == 200


# --- POST /api/auth/verify ---


def test_verify_valid_key(client):
    resp = client.post(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"valid": True}


def test_verify_invalid_key(client):
    resp = client.post(
        "/api/auth/verify",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"valid": False}


def test_verify_missing_header(client):
    resp = client.post("/api/auth/verify")
    assert resp.status_code == 200
    assert resp.json() == {"valid": False}


def test_verify_bad_format(client):
    resp = client.post(
        "/api/auth/verify",
        headers={"Authorization": "Basic some-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"valid": False}


def test_verify_no_env_key(monkeypatch):
    monkeypatch.delenv("WEBAPP_API_KEY", raising=False)
    from coffee_pipeline.api.app import app

    with TestClient(app) as c:
        resp = c.post(
            "/api/auth/verify",
            headers={"Authorization": "Bearer anything"},
        )
    assert resp.json() == {"valid": False}
