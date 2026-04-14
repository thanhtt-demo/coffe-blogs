"""Material management: upload, list, get, delete research materials.

Materials live in ``pipeline/materials/`` with file blobs stored under
``files/`` and a single ``metadata.json`` that tracks every material's
metadata.  This module provides the I/O layer that the REST routes
delegate to.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from coffee_pipeline.api.models import (
    ALLOWED_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_TEXT_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    MaterialContent,
    MaterialMetadata,
    MaterialType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _material_type_from_ext(ext: str) -> MaterialType:
    """Return ``MaterialType.TEXT`` or ``IMAGE`` based on file extension."""
    if ext in ALLOWED_TEXT_EXTENSIONS:
        return MaterialType.TEXT
    return MaterialType.IMAGE


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text content from a PDF file using PyMuPDF.

    Returns concatenated text from all pages, or empty string on failure.
    """
    try:
        import pymupdf

        text_parts: list[str] = []
        with pymupdf.open(str(file_path)) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n".join(text_parts).strip()
    except Exception:
        logger.warning("Cannot extract text from PDF %s", file_path)
        return ""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class MaterialManager:
    """Manages research materials on the local filesystem."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent / "materials"

        self._base_dir = base_dir
        self._files_dir = base_dir / "files"
        self._metadata_path = base_dir / "metadata.json"

        # Ensure directories exist.
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._files_dir.mkdir(parents=True, exist_ok=True)

        # Load existing metadata.
        self._materials: dict[str, MaterialMetadata] = {}
        self._load_metadata()

    # -- Persistence --------------------------------------------------------

    def _load_metadata(self) -> None:
        """Read metadata.json into memory, or initialise empty on failure."""
        if not self._metadata_path.is_file():
            logger.info("metadata.json not found – starting with empty library")
            return

        try:
            raw = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            for item in raw.get("materials", []):
                mat = MaterialMetadata(**item)
                self._materials[mat.id] = mat
        except Exception:
            logger.warning(
                "metadata.json is corrupt or unreadable – starting with empty library"
            )
            self._materials = {}

    def _save_metadata(self) -> None:
        """Write all metadata to metadata.json atomically."""
        data = {
            "materials": [
                m.model_dump(mode="json") for m in self._materials.values()
            ]
        }
        tmp_path = self._metadata_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._metadata_path)

    # -- Upload -------------------------------------------------------------

    def upload(
        self,
        file_bytes: bytes,
        filename: str,
        name: str,
        description: str = "",
    ) -> MaterialMetadata:
        """Validate, persist, and register a new material.

        Returns the created ``MaterialMetadata``.

        Raises ``ValueError`` for invalid extension, empty file, or size
        exceeded.
        """
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(
                f"Định dạng '{ext}' không được hỗ trợ. Chấp nhận: {allowed}"
            )

        if not file_bytes:
            raise ValueError(f"File rỗng: {filename}")

        if len(file_bytes) > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ValueError(
                f"File vượt quá giới hạn {max_mb} MB: {filename}"
            )

        material_id = str(uuid.uuid4())
        file_type = _material_type_from_ext(ext)

        # Persist file blob.
        dest = self._files_dir / f"{material_id}{ext}"
        dest.write_bytes(file_bytes)

        metadata = MaterialMetadata(
            id=material_id,
            name=name,
            description=description,
            file_type=file_type,
            file_extension=ext,
            file_size=len(file_bytes),
            original_filename=filename,
            created_at=datetime.now(timezone.utc),
        )

        self._materials[material_id] = metadata
        self._save_metadata()
        return metadata

    # -- List / Get ---------------------------------------------------------

    def list_materials(
        self, type_filter: str | None = None
    ) -> list[MaterialMetadata]:
        """Return all materials, optionally filtered by type ("text"/"image")."""
        materials = list(self._materials.values())
        if type_filter:
            materials = [m for m in materials if m.file_type.value == type_filter]
        return materials

    def get_material(self, material_id: str) -> MaterialMetadata | None:
        """Return metadata for *material_id*, or ``None``."""
        return self._materials.get(material_id)

    # -- Delete -------------------------------------------------------------

    def delete_material(self, material_id: str) -> None:
        """Remove a material's file and metadata.

        Raises ``FileNotFoundError`` when *material_id* does not exist.
        """
        meta = self._materials.get(material_id)
        if meta is None:
            raise FileNotFoundError(f"Material not found: {material_id}")

        # Remove file from disk.
        file_path = self._files_dir / f"{material_id}{meta.file_extension}"
        if file_path.is_file():
            file_path.unlink()

        del self._materials[material_id]
        self._save_metadata()

    # -- File access --------------------------------------------------------

    def get_file_path(self, material_id: str) -> Path | None:
        """Return the on-disk ``Path`` for a material, or ``None``."""
        meta = self._materials.get(material_id)
        if meta is None:
            return None
        return self._files_dir / f"{material_id}{meta.file_extension}"

    # -- Content reading ----------------------------------------------------

    def save_extracted_text(self, material_id: str, text: str) -> None:
        """Persist extracted text into metadata so it can be reused later."""
        meta = self._materials.get(material_id)
        if meta is None:
            raise FileNotFoundError(f"Material not found: {material_id}")
        meta.extracted_text = text
        meta.extracted = True
        self._save_metadata()

    def save_translated_text(self, material_id: str, text: str) -> None:
        """Persist translated text into metadata so it can be reused later."""
        meta = self._materials.get(material_id)
        if meta is None:
            raise FileNotFoundError(f"Material not found: {material_id}")
        meta.translated_text = text
        self._save_metadata()

    def read_material_content(
        self, material_id: str
    ) -> MaterialContent | None:
        """Read material content for pipeline consumption.

        If the material already has ``extracted_text`` cached, return that
        directly (avoids re-calling LLM for images or re-parsing PDFs).

        Otherwise:
        * Text materials (.txt, .md) → read as UTF-8 string.
        * PDF materials (.pdf) → extract text via PyMuPDF.
        * Image materials → return file_path (caller must run vision separately).

        Returns ``None`` when the material does not exist.
        """
        meta = self._materials.get(material_id)
        if meta is None:
            return None

        # Use cached extracted text if available
        if meta.extracted and meta.extracted_text:
            return MaterialContent(
                id=meta.id,
                name=meta.name,
                description=meta.description,
                file_type=meta.file_type,
                content=meta.extracted_text,
            )

        file_path = self._files_dir / f"{material_id}{meta.file_extension}"

        if meta.file_type == MaterialType.TEXT:
            if meta.file_extension == ".pdf":
                content = _extract_pdf_text(file_path)
            else:
                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception:
                    logger.warning("Cannot read text material %s", material_id)
                    content = ""
            return MaterialContent(
                id=meta.id,
                name=meta.name,
                description=meta.description,
                file_type=meta.file_type,
                content=content,
            )

        # Image material — return file path; vision description happens in
        # extract endpoint or extract_node.
        return MaterialContent(
            id=meta.id,
            name=meta.name,
            description=meta.description,
            file_type=meta.file_type,
            file_path=str(file_path),
        )
