"""In-memory job manager for pipeline execution and progress tracking."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler

from coffee_pipeline.api.models import JobStatus, PipelineJob
from coffee_pipeline.graph import build_graph
from coffee_pipeline.local_images import localize_markdown_images
from coffee_pipeline.utils import (
    derive_filename,
    format_with_prettier,
    repo_root,
    save_pipeline_cache,
    strip_code_fence,
)

PIPELINE_STEPS = [
    "query_gen",
    "research",
    "extract",
    "outline",
    "image_fetch",
    "draft",
    "review",
    "rewrite",
]

POSTS_DIR = repo_root() / "src" / "data" / "post"


class PipelineProgressHandler(BaseCallbackHandler):
    """LangGraph callback that updates job progress on each node transition."""

    def __init__(self, job: PipelineJob, sse_buffer: list[dict]) -> None:
        self.job = job
        self._sse_buffer = sse_buffer

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:  # noqa: ANN003
        # LangGraph may pass node name via serialized["name"], kwargs["name"],
        # or inside tags like "graph:step:2".  Try all approaches.
        node_name = ""

        if serialized is not None:
            node_name = serialized.get("name", "")

        # Fallback: check kwargs["name"] (LangGraph >=0.2)
        if node_name not in PIPELINE_STEPS:
            node_name = kwargs.get("name", "")

        # Fallback: parse from tags (e.g. ["graph:step:2"])
        if node_name not in PIPELINE_STEPS:
            for tag in kwargs.get("tags", []):
                if tag in PIPELINE_STEPS:
                    node_name = tag
                    break

        if node_name in PIPELINE_STEPS:
            idx = PIPELINE_STEPS.index(node_name)
            self.job.current_step = node_name
            self.job.progress = (idx + 1) / len(PIPELINE_STEPS)
            self._sse_buffer.append(
                {
                    "step": node_name,
                    "progress": self.job.progress,
                    "status": self.job.status.value,
                }
            )


class JobManager:
    """Manages pipeline jobs with in-memory storage and SSE event buffering."""

    def __init__(self) -> None:
        self.jobs: dict[str, PipelineJob] = {}
        self._sse_events: dict[str, list[dict]] = {}
        self._user_materials: dict[str, list[dict]] = {}

    def create_job(
        self,
        topic: str,
        user_materials: list[dict] | None = None,
        research_sources: list[str] | None = None,
    ) -> PipelineJob:
        """Create a new pipeline job and start execution in the background."""
        from coffee_pipeline.api.models import ALL_RESEARCH_SOURCES

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        materials = user_materials or []
        material_ids = [m["id"] for m in materials if "id" in m]
        sources = research_sources if research_sources is not None else list(ALL_RESEARCH_SOURCES)
        job = PipelineJob(
            id=job_id,
            topic=topic,
            status=JobStatus.PENDING,
            material_ids=material_ids,
            research_sources=sources,
            created_at=now,
        )
        self.jobs[job_id] = job
        self._sse_events[job_id] = []
        self._user_materials[job_id] = materials
        asyncio.create_task(self._execute_pipeline(job))
        return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        """Return a job by ID, or None if not found."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[PipelineJob]:
        """Return all jobs, newest first."""
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def get_sse_events(self, job_id: str) -> list[dict]:
        """Return buffered SSE events for a job (supports late subscribers)."""
        return list(self._sse_events.get(job_id, []))

    # ------------------------------------------------------------------
    # Internal pipeline execution
    # ------------------------------------------------------------------

    def _run_sync_pipeline(self, job: PipelineJob) -> dict:
        """Run the synchronous LangGraph pipeline (called inside a thread)."""
        handler = PipelineProgressHandler(job, self._sse_events[job.id])
        graph = build_graph()
        user_materials = self._user_materials.get(job.id, [])
        initial_state = {
            "topic": job.topic,
            "category": "",
            "search_results": [],
            "extracted_docs": [],
            "draft_post": "",
            "user_materials": user_materials,
            "research_sources": job.research_sources,
        }
        return graph.invoke(initial_state, config={"callbacks": [handler]})

    async def _execute_pipeline(self, job: PipelineJob) -> None:
        """Execute the pipeline in a background thread and post-process results."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._sse_events[job.id].append(
            {"step": None, "progress": 0.0, "status": job.status.value}
        )

        try:
            final_state = await asyncio.to_thread(self._run_sync_pipeline, job)

            # Post-processing (mirrors cli.py logic)
            draft = final_state.get("draft_post", "")
            if not draft:
                raise RuntimeError("Pipeline produced no article content")

            draft = strip_code_fence(draft)
            filename = derive_filename(draft, job.topic)
            slug = Path(filename).stem

            draft, _ = localize_markdown_images(draft, slug)
            POSTS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = POSTS_DIR / filename
            output_path.write_text(draft, encoding="utf-8")
            format_with_prettier(output_path)

            save_pipeline_cache(job.topic, final_state)

            job.article_id = slug
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0
            self._sse_events[job.id].append(
                {
                    "step": "rewrite",
                    "progress": 1.0,
                    "status": job.status.value,
                    "article_id": slug,
                }
            )

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            self._sse_events[job.id].append(
                {
                    "step": job.current_step,
                    "progress": job.progress,
                    "status": job.status.value,
                    "error": str(exc),
                }
            )
