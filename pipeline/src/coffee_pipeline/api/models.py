"""Pydantic request/response models for the Pipeline Webapp API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Material constants ---

ALLOWED_TEXT_EXTENSIONS: set[str] = {".txt", ".md", ".pdf"}
ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_EXTENSIONS: set[str] = ALLOWED_TEXT_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20 MB


# --- Material models ---


class MaterialType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class MaterialMetadata(BaseModel):
    id: str
    name: str
    description: str = ""
    file_type: MaterialType
    file_extension: str
    file_size: int
    original_filename: str
    created_at: datetime
    extracted: bool = False
    extracted_text: str = ""
    translated_text: str = ""


class MaterialContent(BaseModel):
    id: str
    name: str
    description: str
    file_type: MaterialType
    content: str = ""
    file_path: str = ""


# --- Research source defaults ---

ALL_RESEARCH_SOURCES: list[str] = ["arxiv", "openalex", "web", "youtube"]


# --- Job / Pipeline models ---


class CreateJobRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    material_ids: list[str] = []
    research_sources: list[str] = Field(default_factory=lambda: list(ALL_RESEARCH_SOURCES))


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineJob(BaseModel):
    id: str
    topic: str
    status: JobStatus
    material_ids: list[str] = []
    research_sources: list[str] = Field(default_factory=lambda: list(ALL_RESEARCH_SOURCES))
    current_step: str | None = None
    progress: float = 0.0
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    article_id: str | None = None


class ArticleFrontmatter(BaseModel):
    title: str = Field(..., min_length=1)
    publishDate: datetime
    excerpt: str
    image: str | None = None
    imageSourceId: str | None = None
    category: str | None = None
    tags: list[str] = []
    author: str = "Ba Tê"
    draft: bool = False
    references: list[dict] = []


class ArticleResponse(BaseModel):
    slug: str
    frontmatter: ArticleFrontmatter
    content: str
    has_draft: bool


class UpdateArticleRequest(BaseModel):
    frontmatter: ArticleFrontmatter
    content: str


class PublishResult(BaseModel):
    success: bool
    message: str
    commit_hash: str | None = None


# --- Rewrite models ---


class RewriteComment(BaseModel):
    selected_text: str = Field(..., min_length=1)
    comment: str = Field(..., min_length=1)


class RewriteRequest(BaseModel):
    comments: list[RewriteComment] = Field(..., min_length=1)
    full_content: str = Field(..., min_length=1)


class RewriteResponse(BaseModel):
    rewritten_content: str
