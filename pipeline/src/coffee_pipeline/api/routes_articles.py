"""Article API routes — list, detail, update, delete, and publish."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from coffee_pipeline.api.auth import verify_api_key
from coffee_pipeline.api.models import (
    ArticleResponse,
    PublishResult,
    RewriteRequest,
    RewriteResponse,
    UpdateArticleRequest,
)
from coffee_pipeline.llm import call_llm

router = APIRouter(prefix="/api/articles")


def _get_article_manager(request: Request):
    """Retrieve the ArticleManager instance from app state."""
    return request.app.state.article_manager


def _get_git_manager(request: Request):
    """Retrieve the GitManager instance from app state."""
    return request.app.state.git_manager


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    request: Request,
    category: str | None = None,
):
    """List all articles, optionally filtered by category."""
    article_manager = _get_article_manager(request)
    return article_manager.list_articles(category=category)


@router.get("/{slug}", response_model=ArticleResponse)
async def get_article(slug: str, request: Request):
    """Get a single article by slug."""
    article_manager = _get_article_manager(request)
    article = article_manager.get_article(slug)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {slug}",
        )
    return article


@router.put(
    "/{slug}",
    response_model=ArticleResponse,
    dependencies=[Depends(verify_api_key)],
)
async def update_article(
    slug: str,
    body: UpdateArticleRequest,
    request: Request,
):
    """Update an existing article's frontmatter and content."""
    article_manager = _get_article_manager(request)
    try:
        return article_manager.update_article(
            slug,
            frontmatter=body.frontmatter,
            content=body.content,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {slug}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/{slug}",
    dependencies=[Depends(verify_api_key)],
)
async def delete_article(slug: str, request: Request):
    """Delete an article and its associated assets."""
    article_manager = _get_article_manager(request)
    try:
        article_manager.delete_article(slug)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {slug}",
        )
    return {"detail": f"Article deleted: {slug}"}


@router.post(
    "/{slug}/publish",
    response_model=PublishResult,
    dependencies=[Depends(verify_api_key)],
)
async def publish_article(slug: str, request: Request):
    """Publish an article via git add/commit/push."""
    git_manager = _get_git_manager(request)
    try:
        return git_manager.publish(slug)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {slug}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


_REWRITE_SYSTEM_PROMPT = (
    "Bạn là một biên tập viên chuyên nghiệp. Nhiệm vụ của bạn là viết lại các đoạn văn bản\n"
    "trong bài viết theo chỉ dẫn từ người biên tập.\n"
    "\n"
    "Quy tắc:\n"
    "- Chỉ thay đổi các đoạn văn bản được chỉ định, giữ nguyên phần còn lại.\n"
    "- Giữ nguyên format Markdown (headings, links, bold, italic, lists).\n"
    "- Giữ nguyên ngôn ngữ gốc của bài viết.\n"
    "- Trả về TOÀN BỘ nội dung bài viết đã chỉnh sửa, không chỉ các đoạn thay đổi.\n"
    "- KHÔNG thêm giải thích, KHÔNG wrap trong code fence. Chỉ trả về nội dung bài viết."
)


def _build_user_prompt(full_content: str, comments: list) -> str:
    """Build the user prompt listing all rewrite instructions."""
    parts = [f"Nội dung bài viết:\n---\n{full_content}\n---\n\nCác đoạn cần viết lại:\n"]
    for i, c in enumerate(comments, 1):
        parts.append(f'{i}. Đoạn: "{c.selected_text}"\n   Chỉ dẫn: {c.comment}\n')
    parts.append(
        "Hãy viết lại các đoạn trên theo chỉ dẫn và trả về toàn bộ nội dung bài viết đã chỉnh sửa."
    )
    return "\n".join(parts)


@router.post(
    "/{slug}/rewrite",
    response_model=RewriteResponse,
    dependencies=[Depends(verify_api_key)],
)
async def rewrite_article(slug: str, body: RewriteRequest):
    """Rewrite article sections based on inline comments via LLM."""
    user_prompt = _build_user_prompt(body.full_content, body.comments)
    try:
        text, _usage = call_llm(
            system=_REWRITE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            temperature=0.3,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM xử lý thất bại: {exc}",
        )
    return RewriteResponse(rewritten_content=text)
