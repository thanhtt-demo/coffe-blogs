"""Property-based and integration tests for material API endpoints.

Uses Hypothesis to verify correctness properties of the material REST API
and FastAPI TestClient for integration tests.

Validates: Requirements 6.1, 6.4, 6.6
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from coffee_pipeline.api.material_manager import MaterialManager
from coffee_pipeline.api.models import MaterialType

TEST_API_KEY = "test-materials-key-42"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Create a TestClient with a temp-dir-based MaterialManager."""
    monkeypatch.setenv("WEBAPP_API_KEY", TEST_API_KEY)
    from coffee_pipeline.api.app import app

    with TestClient(app) as c:
        # Override the material_manager with a temp-dir-based one
        app.state.material_manager = MaterialManager(base_dir=tmp_path / "materials")
        yield c


def _auth_header():
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


def _upload_file(client, filename="test.txt", content=b"hello world", name="Test Material", description=""):
    """Helper to upload a file via the API. Returns the response."""
    return client.post(
        "/api/materials/upload",
        headers=_auth_header(),
        files=[("files", (filename, content))],
        data={"name": name, "description": description},
    )


def _upload_file_meta(client, **kwargs):
    """Upload a single file and return the first MaterialMetadata dict."""
    resp = _upload_file(client, **kwargs)
    assert resp.status_code == 201
    body = resp.json()
    return body[0] if isinstance(body, list) else body


# ---------------------------------------------------------------------------
# Property 12: Mutating endpoints require auth
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 12: Mutating endpoints require auth


class TestMutatingEndpointsRequireAuth:
    """Property 12: Mutating material endpoints require auth — POST upload
    and DELETE without auth header → 401.

    **Validates: Requirements 6.1, 6.4**
    """

    @given(material_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_upload_without_auth_returns_401(self, material_id, client):
        """POST /api/materials/upload without auth → 401."""
        resp = client.post(
            "/api/materials/upload",
            files=[("files", ("test.txt", b"some content"))],
            data={"name": "Test"},
        )
        assert resp.status_code == 401

    @given(material_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_delete_without_auth_returns_401(self, material_id, client):
        """DELETE /api/materials/{id} without auth → 401."""
        resp = client.delete(f"/api/materials/{material_id}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Property 13: Non-existent material ID returns 404
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 13: Non-existent material ID returns 404


class TestNonExistentMaterialReturns404:
    """Property 13: Non-existent material ID returns 404 — GET, DELETE (with
    auth), and GET file with random UUIDs that don't exist → all return 404.

    **Validates: Requirements 6.6**
    """

    @given(material_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_get_nonexistent_returns_404(self, material_id, client):
        """GET /api/materials/{id} with non-existent UUID → 404."""
        resp = client.get(f"/api/materials/{material_id}")
        assert resp.status_code == 404

    @given(material_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_delete_nonexistent_returns_404(self, material_id, client):
        """DELETE /api/materials/{id} (with auth) with non-existent UUID → 404."""
        resp = client.delete(
            f"/api/materials/{material_id}",
            headers=_auth_header(),
        )
        assert resp.status_code == 404

    @given(material_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_get_file_nonexistent_returns_404(self, material_id, client):
        """GET /api/materials/{id}/file with non-existent UUID → 404."""
        resp = client.get(f"/api/materials/{material_id}/file")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration tests — basic CRUD flows
# ---------------------------------------------------------------------------


class TestMaterialCRUDIntegration:
    """Integration tests for material API endpoints covering upload, list,
    get, get file, delete, filter, and error cases."""

    def test_upload_valid_txt_returns_201(self, client):
        """Upload a valid .txt file with auth → 201 with correct metadata."""
        resp = _upload_file(client, filename="notes.txt", content=b"My research notes", name="Research Notes", description="Some notes")
        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        meta = body[0]
        assert meta["name"] == "Research Notes"
        assert meta["description"] == "Some notes"
        assert meta["file_type"] == "text"
        assert meta["file_extension"] == ".txt"
        assert meta["file_size"] == len(b"My research notes")
        assert meta["original_filename"] == "notes.txt"
        assert "id" in meta

    def test_list_materials_returns_uploaded(self, client):
        """GET /api/materials → returns uploaded material."""
        _upload_file(client, name="Listed Material")
        resp = client.get("/api/materials")
        assert resp.status_code == 200
        materials = resp.json()
        assert len(materials) == 1
        assert materials[0]["name"] == "Listed Material"

    def test_get_material_by_id(self, client):
        """GET /api/materials/{id} → returns metadata."""
        meta = _upload_file_meta(client, name="Get By ID")
        resp = client.get(f"/api/materials/{meta['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get By ID"
        assert resp.json()["id"] == meta["id"]

    def test_get_material_file(self, client):
        """GET /api/materials/{id}/file → returns file content."""
        content = b"File content for download"
        meta = _upload_file_meta(client, content=content, name="Download Test")
        resp = client.get(f"/api/materials/{meta['id']}/file")
        assert resp.status_code == 200
        assert resp.content == content

    def test_delete_material_with_auth(self, client):
        """DELETE /api/materials/{id} with auth → 200."""
        meta = _upload_file_meta(client, name="To Delete")
        resp = client.delete(
            f"/api/materials/{meta['id']}",
            headers=_auth_header(),
        )
        assert resp.status_code == 200
        # Verify it's gone
        get_resp = client.get(f"/api/materials/{meta['id']}")
        assert get_resp.status_code == 404

    def test_list_materials_with_type_filter(self, client):
        """GET /api/materials?type=text → filtered results."""
        _upload_file(client, filename="doc.txt", content=b"text content", name="Text Doc")
        _upload_file(client, filename="photo.jpg", content=b"\xff\xd8\xff\xe0", name="Photo")

        text_resp = client.get("/api/materials?type=text")
        assert text_resp.status_code == 200
        text_materials = text_resp.json()
        assert len(text_materials) == 1
        assert text_materials[0]["file_type"] == "text"

        image_resp = client.get("/api/materials?type=image")
        assert image_resp.status_code == 200
        image_materials = image_resp.json()
        assert len(image_materials) == 1
        assert image_materials[0]["file_type"] == "image"

    def test_upload_without_name_returns_400(self, client):
        """Upload without name → 400."""
        resp = client.post(
            "/api/materials/upload",
            headers=_auth_header(),
            files=[("files", ("test.txt", b"content"))],
            data={"name": "", "description": ""},
        )
        assert resp.status_code == 400

    def test_upload_invalid_extension_returns_400(self, client):
        """Upload with invalid extension → 400."""
        resp = client.post(
            "/api/materials/upload",
            headers=_auth_header(),
            files=[("files", ("script.exe", b"binary stuff"))],
            data={"name": "Bad File"},
        )
        assert resp.status_code == 400

    def test_upload_multiple_files_returns_201(self, client):
        """Upload multiple files in one request → 201 with list of metadata."""
        resp = client.post(
            "/api/materials/upload",
            headers=_auth_header(),
            files=[
                ("files", ("doc1.txt", b"content one")),
                ("files", ("doc2.md", b"content two")),
                ("files", ("photo.jpg", b"\xff\xd8\xff\xe0")),
            ],
            data={"name": "Batch Upload", "description": "Multiple files"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3
        assert all(m["name"] == "Batch Upload" for m in body)
        extensions = {m["file_extension"] for m in body}
        assert extensions == {".txt", ".md", ".jpg"}
