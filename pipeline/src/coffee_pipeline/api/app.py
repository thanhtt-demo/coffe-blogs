"""FastAPI application for the Pipeline Webapp API.

Mounts job and article routers, configures CORS, and initialises
managers (JobManager, ArticleManager, GitManager) via the lifespan
context manager.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from coffee_pipeline.api.article_manager import ArticleManager
from coffee_pipeline.api.git_manager import GitManager
from coffee_pipeline.api.job_manager import JobManager
from coffee_pipeline.api.material_manager import MaterialManager
from coffee_pipeline.api.routes_articles import router as articles_router
from coffee_pipeline.api.routes_jobs import router as jobs_router
from coffee_pipeline.api.routes_materials import router as materials_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared managers on startup and clean up on shutdown."""
    app.state.job_manager = JobManager()
    app.state.article_manager = ArticleManager()
    app.state.git_manager = GitManager()
    app.state.material_manager = MaterialManager()
    yield


app = FastAPI(title="Ba Tê Pipeline API", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS — allow all origins in dev mode
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------
app.include_router(jobs_router)
app.include_router(articles_router)
app.include_router(materials_router)


# ---------------------------------------------------------------------------
# Auth verify endpoint
# ---------------------------------------------------------------------------

@app.post("/api/auth/verify")
async def verify_auth(authorization: str | None = Header(default=None)):
    """Check whether the provided API key is valid.

    Accepts ``Authorization: Bearer {key}`` header.
    Returns ``{"valid": true}`` when the key matches ``WEBAPP_API_KEY``,
    ``{"valid": false}`` otherwise.
    """
    expected = os.environ.get("WEBAPP_API_KEY", "")

    if not authorization or not expected:
        return {"valid": False}

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return {"valid": False}

    return {"valid": parts[1] == expected}
