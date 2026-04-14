"""Property-based tests for job creation with material_ids.

Uses Hypothesis to verify correctness properties of the POST /api/jobs
endpoint when material_ids are provided.

Validates: Requirements 3.5, 3.6, 7.2, 7.4
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from coffee_pipeline.api.material_manager import MaterialManager

TEST_API_KEY = "test-job-materials-key-77"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Create a TestClient with a temp-dir-based MaterialManager and dry-run pipeline."""
    monkeypatch.setenv("WEBAPP_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("PIPELINE_DRY_RUN", "1")

    from coffee_pipeline.api.app import app

    with TestClient(app) as c:
        app.state.material_manager = MaterialManager(base_dir=tmp_path / "materials")
        yield c


def _auth_header():
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


def _upload_material(client, filename="note.txt", content=b"some research content", name="Test Note"):
    """Upload a material via the API and return the first metadata dict."""
    resp = client.post(
        "/api/materials/upload",
        headers=_auth_header(),
        files=[("files", (filename, content))],
        data={"name": name, "description": "test desc"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body[0] if isinstance(body, list) else body


# ---------------------------------------------------------------------------
# Property 6: Invalid material_ids rejected
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 6: Invalid material_ids rejected


class TestInvalidMaterialIdsRejected:
    """Property 6: POST /api/jobs with material_ids containing at least one
    UUID that doesn't exist in MaterialLibrary → 400 with message listing
    invalid IDs.

    **Validates: Requirements 3.5**
    """

    @given(fake_ids=st.lists(st.uuids().map(str), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_nonexistent_material_ids_return_400(self, fake_ids, client):
        """POST /api/jobs with non-existent material_ids → 400."""
        resp = client.post(
            "/api/jobs",
            json={"topic": "Cà phê Việt Nam", "material_ids": fake_ids},
            headers=_auth_header(),
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        # Every fake ID should appear in the error message
        for fid in fake_ids:
            assert fid in detail

    @given(fake_id=st.uuids().map(str))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mix_valid_and_invalid_ids_return_400(self, fake_id, client):
        """Upload a real material, then create job with one valid + one invalid ID → 400."""
        real = _upload_material(client)
        resp = client.post(
            "/api/jobs",
            json={"topic": "Cà phê rang", "material_ids": [real["id"], fake_id]},
            headers=_auth_header(),
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert fake_id in detail


# ---------------------------------------------------------------------------
# Property 7: Empty material_ids preserves existing behavior
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 7: Empty material_ids preserves existing behavior


class TestEmptyMaterialIdsPreservesExistingBehavior:
    """Property 7: POST /api/jobs without material_ids or with empty list
    → 201, job created normally. The pipeline may fail in background (dry-run)
    but the job itself is created with status pending/running.

    **Validates: Requirements 3.6, 7.4**
    """

    @given(topic=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_empty_material_ids_creates_job(self, topic, client):
        """POST /api/jobs with material_ids=[] → 201."""
        resp = client.post(
            "/api/jobs",
            json={"topic": topic, "material_ids": []},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["topic"] == topic
        assert body["status"] in ("pending", "running")
        assert body["material_ids"] == []

    @given(topic=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_material_ids_field_creates_job(self, topic, client):
        """POST /api/jobs without material_ids field → 201."""
        resp = client.post(
            "/api/jobs",
            json={"topic": topic},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["topic"] == topic
        assert body["status"] in ("pending", "running")
        assert body["material_ids"] == []


# ---------------------------------------------------------------------------
# Property 15: material_ids resolved to user_materials
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 15: material_ids resolved to user_materials


class TestMaterialIdsResolvedToUserMaterials:
    """Property 15: Upload materials first, then create a job with those
    material_ids. Verify the job is created (201) and the job's material_ids
    field contains the expected IDs.

    **Validates: Requirements 7.2**
    """

    @given(data=st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_material_ids_create_job_with_ids(self, data, client):
        """Upload 1-3 materials, create job referencing them → 201 with correct material_ids."""
        count = data.draw(st.integers(min_value=1, max_value=3))
        uploaded_ids = []
        for i in range(count):
            mat = _upload_material(
                client,
                filename=f"doc{i}.txt",
                content=f"content for material {i}".encode(),
                name=f"Material {i}",
            )
            uploaded_ids.append(mat["id"])

        resp = client.post(
            "/api/jobs",
            json={"topic": "Cà phê đặc sản", "material_ids": uploaded_ids},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] in ("pending", "running")
        assert set(body["material_ids"]) == set(uploaded_ids)

    def test_single_material_resolved(self, client):
        """Upload one text material, create job → material_ids contains that ID."""
        mat = _upload_material(client, filename="research.md", content=b"# Research\nSome findings", name="Research Doc")
        resp = client.post(
            "/api/jobs",
            json={"topic": "Lịch sử cà phê", "material_ids": [mat["id"]]},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["material_ids"] == [mat["id"]]

    def test_image_material_resolved(self, client):
        """Upload an image material, create job → material_ids contains that ID."""
        mat = _upload_material(client, filename="photo.jpg", content=b"\xff\xd8\xff\xe0fake-jpg", name="Coffee Photo")
        resp = client.post(
            "/api/jobs",
            json={"topic": "Hạt cà phê Robusta", "material_ids": [mat["id"]]},
            headers=_auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["material_ids"] == [mat["id"]]
