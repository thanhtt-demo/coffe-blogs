"""Job API routes — create, list, get, and SSE stream for pipeline jobs."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from coffee_pipeline.api.auth import verify_api_key
from coffee_pipeline.api.models import CreateJobRequest, PipelineJob

router = APIRouter(prefix="/api/jobs")


def _get_job_manager(request: Request):
    """Retrieve the JobManager instance from app state."""
    return request.app.state.job_manager


def _get_material_manager(request: Request):
    """Retrieve the MaterialManager instance from app state."""
    return request.app.state.material_manager


@router.post(
    "",
    response_model=PipelineJob,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_job(
    body: CreateJobRequest,
    request: Request,
):
    """Create a new pipeline job and start execution in the background."""
    job_manager = _get_job_manager(request)

    user_materials: list[dict] = []

    if body.material_ids:
        material_manager = _get_material_manager(request)

        # Validate all IDs exist
        invalid_ids = [
            mid for mid in body.material_ids
            if material_manager.get_material(mid) is None
        ]
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Material không tồn tại: {', '.join(invalid_ids)}",
            )

        # Read content for each valid material
        for mid in body.material_ids:
            content = material_manager.read_material_content(mid)
            if content is not None:
                user_materials.append(content.model_dump())

    job = job_manager.create_job(
        body.topic,
        user_materials=user_materials,
        research_sources=body.research_sources,
    )
    return job


@router.get("", response_model=list[PipelineJob])
async def list_jobs(request: Request):
    """List all pipeline jobs, newest first."""
    job_manager = _get_job_manager(request)
    return job_manager.list_jobs()


@router.get("/{job_id}", response_model=PipelineJob)
async def get_job(job_id: str, request: Request):
    """Get a single pipeline job by ID."""
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, request: Request):
    """SSE endpoint that pushes events on node transitions.

    Polls ``job.get_sse_events()`` every 1 second, yields new events as JSON,
    and closes the stream when the job reaches *completed* or *failed* status.
    """
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    async def _event_generator():
        last_index = 0
        while True:
            events = job_manager.get_sse_events(job_id)
            new_events = events[last_index:]
            for event in new_events:
                yield {"data": json.dumps(event)}
            last_index = len(events)

            # Check terminal state *after* flushing remaining events
            current_job = job_manager.get_job(job_id)
            if current_job and current_job.status.value in ("completed", "failed"):
                break

            await asyncio.sleep(1)

    return EventSourceResponse(_event_generator())
