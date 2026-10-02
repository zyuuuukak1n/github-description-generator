"""FastAPI application entrypoint with security middleware, defensive handling, and routing."""

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.ai_service import AIService
from app.config import get_settings
from app.github_service import GitHubAPIError, GitHubService
from app.logging_config import setup_logging
from app.schemas import (
    AnalyzeRepoRequest,
    AnalyzeRepoResponse,
    ErrorResponse,
    UpdateRepoDescriptionRequest,
    UpdateRepoDescriptionResponse,
)

settings = get_settings()
logger = setup_logging(settings.LOG_LEVEL)

# Rate limiter setup
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.APP_ENV != "production" else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
origins = settings.CORS_ORIGINS
if isinstance(origins, str):
    origins = [origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Services
github_service = GitHubService(default_token=settings.GITHUB_DEFAULT_TOKEN)
ai_service = AIService(
    gemini_api_key=settings.GEMINI_API_KEY,
    gemini_model=settings.GEMINI_MODEL,
    openai_api_key=settings.OPENAI_API_KEY,
    openai_model=settings.OPENAI_MODEL,
)

# Static files path resolution
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


# ------------------------------------------------------------------------------
# Security Middlewares & Headers
# ------------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers_and_timing(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Add standard security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Process-Time"] = f"{duration:.3f}s"
    return response


# ------------------------------------------------------------------------------
# Exception Handlers (Defensive: Mask internal details from public responses)
# ------------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_msg = errors[0].get("msg", "入力内容に不備があります。") if errors else "入力値エラー"
    field = ".".join(str(x) for x in errors[0].get("loc", [])) if errors else ""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            success=False,
            error=f"入力値が無効です: {first_msg}" + (f" ({field})" if field else ""),
            detail=str(errors),
        ).model_dump(),
    )


@app.exception_handler(GitHubAPIError)
async def github_api_exception_handler(request: Request, exc: GitHubAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=exc.message,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    err_text = (
        exc.detail if isinstance(exc.detail, str)
        else "リクエスト処理中にエラーが発生しました。"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=err_text,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    logger.error("Unhandled Server Error [ID: %s]: %s", error_id, str(exc), exc_info=True)
    # Mask internal stack traces from client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            error="システム内部で予期せぬエラーが発生しました。管理者へお問い合わせください。",
            error_id=error_id,
        ).model_dump(),
    )


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@app.api_route("/health", methods=["GET", "HEAD"], tags=["Monitoring"])
async def health_check():
    """Health check endpoint for Apache2 reverse proxy and monitoring tools."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "ai_engine": (
            "gemini" if settings.GEMINI_API_KEY
            else ("openai" if settings.OPENAI_API_KEY else "heuristic")
        ),
    }


@app.post(
    "/api/analyze",
    response_model=AnalyzeRepoResponse,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Repository Analysis"],
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def analyze_repository(request: Request, payload: AnalyzeRepoRequest):
    """
    Analyze a GitHub public repository and generate suggested descriptions & topics.
    """
    owner, repo = payload.repo_input.split("/")
    logger.info("Analyzing repository: %s/%s", owner, repo)

    # 1. Fetch repo metadata from GitHub API
    meta = await github_service.get_repository_details(owner, repo)

    # 2. Fetch README and file tree in parallel
    readme_content = await github_service.get_repository_readme(owner, repo)
    meta.has_readme = bool(readme_content)
    root_files = await github_service.get_repository_root_files(owner, repo)

    # 3. Generate description and topics via AI/Heuristic engine
    ai_result = await ai_service.generate(
        repo_name=repo,
        owner=owner,
        current_description=meta.description,
        primary_language=meta.language,
        topics=meta.topics,
        readme_content=readme_content,
        root_files=root_files,
        target_language=payload.language,
        requested_tone=payload.tone,
        max_chars=payload.target_char_limit,
    )

    return AnalyzeRepoResponse(
        success=True,
        metadata=meta,
        suggested_description=ai_result["suggested_description"],
        char_count=ai_result["char_count"],
        suggested_topics=ai_result["suggested_topics"],
        alternative_descriptions=ai_result.get("alternative_descriptions", []),
        engine_used=ai_result.get("engine_used", "heuristic"),
    )


@app.post(
    "/api/update",
    response_model=UpdateRepoDescriptionResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Repository Update"],
)
@limiter.limit("15/minute")
async def update_repository_description(
    request: Request,
    payload: UpdateRepoDescriptionRequest,
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
):
    """
    Update GitHub repository description and topics using user-provided PAT.
    Token is never stored on disk or written to log files.
    """
    token = payload.github_token or x_github_token
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リポジトリを更新するには GitHub Personal Access Token (PAT) が必要です。",
        )

    logger.info("Updating description for repository: %s/%s", payload.owner, payload.repo)

    updated_desc, updated_topics = await github_service.update_repository_description(
        owner=payload.owner,
        repo=payload.repo,
        description=payload.description,
        topics=payload.topics,
        token=token.strip(),
    )

    return UpdateRepoDescriptionResponse(
        success=True,
        message=f"リポジトリ '{payload.owner}/{payload.repo}' の説明文を正常に更新しました。",
        current_description=updated_desc,
        current_topics=updated_topics,
        repo_url=f"https://github.com/{payload.owner}/{payload.repo}",
    )


# ------------------------------------------------------------------------------
# Static Files & SPA Frontend Serving
# ------------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"status": "Frontend build files not found."})
