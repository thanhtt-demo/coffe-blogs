"""Property-based tests for MaterialManager.

Uses Hypothesis to verify correctness properties of the MaterialManager
class across randomised inputs.

Validates: Requirements 1.3, 1.4, 1.5, 1.7, 2.2, 2.4, 2.6, 5.1, 5.2, 5.4, 5.6, 6.3, 6.5
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from coffee_pipeline.api.material_manager import MaterialManager
from coffee_pipeline.api.models import (
    ALLOWED_EXTENSIONS,
    MaterialType,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

VALID_EXTENSIONS = st.sampled_from([".txt", ".md", ".pdf", ".jpg", ".jpeg", ".png", ".webp"])
INVALID_EXTENSIONS = st.sampled_from([".exe", ".py", ".zip", ".html", ".csv"])

TEXT_EXTENSIONS = st.sampled_from([".txt", ".md", ".pdf"])
IMAGE_EXTENSIONS = st.sampled_from([".jpg", ".jpeg", ".png", ".webp"])

FILE_CONTENT_TEXT = st.text(min_size=1, max_size=5000).map(lambda s: s.encode("utf-8"))
FILE_CONTENT_IMAGE = st.binary(min_size=1, max_size=5000)

MATERIAL_NAMES = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(categories=("L", "N", "Z")),
)
MATERIAL_DESCRIPTIONS = st.text(min_size=0, max_size=500)


# ---------------------------------------------------------------------------
# Property 1: Upload round-trip
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 1: Upload round-trip


class TestUploadRoundTrip:
    """Property 1: Upload round-trip — upload file rồi get lại, metadata và
    file content phải khớp.

    **Validates: Requirements 1.3, 5.1, 5.2, 5.6, 6.3, 6.5**
    """

    @given(
        ext=VALID_EXTENSIONS,
        content=st.one_of(FILE_CONTENT_TEXT, FILE_CONTENT_IMAGE),
        name=MATERIAL_NAMES,
        description=MATERIAL_DESCRIPTIONS,
    )
    @settings(max_examples=100)
    def test_upload_round_trip(self, ext, content, name, description):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)
            filename = f"testfile{ext}"

            meta = mgr.upload(file_bytes=content, filename=filename, name=name, description=description)

            # Metadata fields must match
            assert meta.name == name
            assert meta.description == description
            assert meta.file_extension == ext
            assert meta.file_size == len(content)

            expected_type = MaterialType.TEXT if ext in {".txt", ".md", ".pdf"} else MaterialType.IMAGE
            assert meta.file_type == expected_type

            # get_material must return matching metadata
            retrieved = mgr.get_material(meta.id)
            assert retrieved is not None
            assert retrieved.name == name
            assert retrieved.description == description
            assert retrieved.file_extension == ext
            assert retrieved.file_size == len(content)
            assert retrieved.file_type == expected_type

            # get_file_path must return a file with identical content
            file_path = mgr.get_file_path(meta.id)
            assert file_path is not None
            assert file_path.is_file()
            assert file_path.read_bytes() == content


# ---------------------------------------------------------------------------
# Property 2: Extension validation
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 2: Extension validation


class TestExtensionValidation:
    """Property 2: Extension validation — chỉ accept extensions trong allowed set.

    **Validates: Requirements 1.4, 1.5**
    """

    @given(ext=VALID_EXTENSIONS, content=FILE_CONTENT_TEXT, name=MATERIAL_NAMES)
    @settings(max_examples=100)
    def test_allowed_extension_succeeds(self, ext, content, name):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)
            meta = mgr.upload(file_bytes=content, filename=f"file{ext}", name=name)
            assert meta.file_extension == ext

    @given(ext=INVALID_EXTENSIONS, content=FILE_CONTENT_TEXT, name=MATERIAL_NAMES)
    @settings(max_examples=100)
    def test_disallowed_extension_raises(self, ext, content, name):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)
            with pytest.raises(ValueError):
                mgr.upload(file_bytes=content, filename=f"file{ext}", name=name)


# ---------------------------------------------------------------------------
# Property 3: Upload returns unique UUIDs
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 3: Upload returns unique UUIDs


class TestUniqueUUIDs:
    """Property 3: Upload returns unique UUIDs — N uploads → N distinct UUID v4.

    **Validates: Requirements 1.7**
    """

    @given(
        files=st.lists(
            st.tuples(VALID_EXTENSIONS, FILE_CONTENT_TEXT, MATERIAL_NAMES),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=100)
    def test_unique_uuids(self, files):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)
            ids: list[str] = []

            for ext, content, name in files:
                meta = mgr.upload(file_bytes=content, filename=f"f{ext}", name=name)
                ids.append(meta.id)

            # All IDs must be distinct
            assert len(ids) == len(set(ids))

            # Each ID must be a valid UUID v4
            for mid in ids:
                parsed = uuid.UUID(mid, version=4)
                assert str(parsed) == mid


# ---------------------------------------------------------------------------
# Property 4: Type filter returns matching materials
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 4: Type filter returns matching materials


class TestTypeFilter:
    """Property 4: Type filter returns matching materials — filter text/image
    trả đúng loại.

    **Validates: Requirements 2.2, 2.6**
    """

    @given(
        text_files=st.lists(
            st.tuples(TEXT_EXTENSIONS, FILE_CONTENT_TEXT, MATERIAL_NAMES),
            min_size=1,
            max_size=5,
        ),
        image_files=st.lists(
            st.tuples(IMAGE_EXTENSIONS, FILE_CONTENT_IMAGE, MATERIAL_NAMES),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_type_filter(self, text_files, image_files):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)

            for ext, content, name in text_files:
                mgr.upload(file_bytes=content, filename=f"t{ext}", name=name)
            for ext, content, name in image_files:
                mgr.upload(file_bytes=content, filename=f"i{ext}", name=name)

            text_results = mgr.list_materials(type_filter="text")
            for m in text_results:
                assert m.file_type == MaterialType.TEXT

            image_results = mgr.list_materials(type_filter="image")
            for m in image_results:
                assert m.file_type == MaterialType.IMAGE

            # Counts should match
            assert len(text_results) == len(text_files)
            assert len(image_results) == len(image_files)


# ---------------------------------------------------------------------------
# Property 5: Delete removes file and metadata
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 5: Delete removes file and metadata


class TestDeleteRemoves:
    """Property 5: Delete removes file and metadata — sau delete, file và
    metadata biến mất.

    **Validates: Requirements 2.4**
    """

    @given(
        ext=VALID_EXTENSIONS,
        content=st.one_of(FILE_CONTENT_TEXT, FILE_CONTENT_IMAGE),
        name=MATERIAL_NAMES,
    )
    @settings(max_examples=100)
    def test_delete_removes(self, ext, content, name):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)
            meta = mgr.upload(file_bytes=content, filename=f"del{ext}", name=name)

            file_path = mgr.get_file_path(meta.id)
            assert file_path is not None and file_path.is_file()

            mgr.delete_material(meta.id)

            # Metadata gone
            assert mgr.get_material(meta.id) is None

            # File gone
            assert not file_path.is_file()


# ---------------------------------------------------------------------------
# Property 14: Metadata persistence round-trip
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 14: Metadata persistence round-trip


class TestMetadataPersistence:
    """Property 14: Metadata persistence round-trip — tạo MaterialManager mới
    phải load lại đúng metadata.

    **Validates: Requirements 5.4**
    """

    @given(
        files=st.lists(
            st.tuples(
                VALID_EXTENSIONS,
                st.one_of(FILE_CONTENT_TEXT, FILE_CONTENT_IMAGE),
                MATERIAL_NAMES,
                MATERIAL_DESCRIPTIONS,
            ),
            min_size=1,
            max_size=8,
        )
    )
    @settings(max_examples=100)
    def test_metadata_persistence(self, files):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "materials"
            mgr = MaterialManager(base_dir=base)

            uploaded = []
            for ext, content, name, desc in files:
                meta = mgr.upload(
                    file_bytes=content, filename=f"p{ext}", name=name, description=desc
                )
                uploaded.append(meta)

            # Create a NEW MaterialManager pointing to the same base_dir
            mgr2 = MaterialManager(base_dir=base)

            for original in uploaded:
                loaded = mgr2.get_material(original.id)
                assert loaded is not None
                assert loaded.name == original.name
                assert loaded.description == original.description
                assert loaded.file_type == original.file_type
                assert loaded.file_extension == original.file_extension
                assert loaded.file_size == original.file_size
                assert loaded.original_filename == original.original_filename
