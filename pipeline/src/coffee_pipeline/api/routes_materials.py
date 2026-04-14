"""Material API routes — upload, list, get, delete, and serve files."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from coffee_pipeline.api.auth import verify_api_key
from coffee_pipeline.api.models import MaterialMetadata

router = APIRouter(prefix="/api/materials", dependencies=[Depends(verify_api_key)])


def _get_material_manager(request: Request):
    """Retrieve the MaterialManager instance from app state."""
    return request.app.state.material_manager


@router.post(
    "/upload",
    response_model=list[MaterialMetadata],
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    request: Request,
    files: list[UploadFile] = File(...),
    name: str = Form(default=""),
    description: str = Form(default=""),
):
    """Upload one or more research materials (multipart form data).

    All files share the same *name* and *description*.
    """
    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên hiển thị là bắt buộc",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất một file",
        )

    material_manager = _get_material_manager(request)
    results: list[MaterialMetadata] = []

    for file in files:
        file_bytes = await file.read()
        try:
            metadata = material_manager.upload(
                file_bytes=file_bytes,
                filename=file.filename or "unknown",
                name=name.strip(),
                description=description,
            )
        except ValueError as exc:
            msg = str(exc)
            if "vượt quá" in msg or "giới hạn" in msg:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=msg,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )
        results.append(metadata)

    return results


@router.get("", response_model=list[MaterialMetadata])
async def list_materials(
    request: Request,
    type: str | None = None,
):
    """List all materials, optionally filtered by type (text/image)."""
    material_manager = _get_material_manager(request)
    return material_manager.list_materials(type_filter=type)


@router.get("/{material_id}", response_model=MaterialMetadata)
async def get_material(material_id: str, request: Request):
    """Get a single material's metadata by ID."""
    material_manager = _get_material_manager(request)
    meta = material_manager.get_material(material_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )
    return meta


@router.delete("/{material_id}")
async def delete_material(material_id: str, request: Request):
    """Delete a material and its file from disk."""
    material_manager = _get_material_manager(request)
    try:
        material_manager.delete_material(material_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )
    return {"detail": "Deleted"}


@router.get("/{material_id}/file")
async def get_material_file(material_id: str, request: Request):
    """Serve the original uploaded file for preview/download."""
    material_manager = _get_material_manager(request)
    meta = material_manager.get_material(material_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    file_path = material_manager.get_file_path(material_id)
    if file_path is None or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    return FileResponse(
        path=str(file_path),
        filename=meta.original_filename,
    )


@router.post("/{material_id}/extract")
async def extract_material_text(material_id: str, request: Request):
    """Extract text content from a material and cache it.

    For images: uses LLM vision. For text/PDF: reads content directly.
    Saves the result into ``extracted_text`` so subsequent calls and
    pipeline runs reuse the cached text without re-calling LLM.
    """
    import asyncio
    from pathlib import Path

    material_manager = _get_material_manager(request)
    meta = material_manager.get_material(material_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Material not found")

    file_path = material_manager.get_file_path(material_id)
    if file_path is None or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    if meta.file_type.value == "image":
        from coffee_pipeline.llm import describe_image

        img_bytes = file_path.read_bytes()
        ext_to_mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime = ext_to_mime.get(meta.file_extension, "image/jpeg")
        context = meta.name
        if meta.description:
            context += f" — {meta.description}"

        content = await asyncio.to_thread(describe_image, img_bytes, mime, context)
    else:
        mc = material_manager.read_material_content(material_id)
        content = mc.content if mc else ""

    # Save extracted text to metadata for reuse
    if content.strip():
        material_manager.save_extracted_text(material_id, content)

    return {"content": content, "extracted": bool(content.strip())}


@router.post("/{material_id}/translate")
async def translate_material_text(material_id: str, request: Request):
    """Translate extracted text to Vietnamese and cache the result."""
    import asyncio

    material_manager = _get_material_manager(request)
    meta = material_manager.get_material(material_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Material not found")

    # Return cached translation if available
    if meta.translated_text:
        return {"translated_text": meta.translated_text}

    # Must have extracted text first
    if not meta.extracted or not meta.extracted_text:
        raise HTTPException(status_code=400, detail="Chưa extract text. Hãy extract trước khi dịch.")

    from coffee_pipeline.llm import call_llm

    system = "Bạn là dịch giả chuyên nghiệp. Dịch chính xác nội dung sang tiếng Việt. Giữ nguyên ý nghĩa, không thêm bớt thông tin."
    user = f"Dịch sang tiếng Việt:\n\n{meta.extracted_text}"

    translated, _ = await asyncio.to_thread(call_llm, system, user, 4096, 0.3)

    if translated.strip():
        material_manager.save_translated_text(material_id, translated.strip())

    return {"translated_text": translated.strip()}
