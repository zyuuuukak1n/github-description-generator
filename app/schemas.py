"""Pydantic schemas with strict defensive validation for requests and responses."""

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# GitHub limits & regex patterns
GITHUB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\.\-]+$")
GITHUB_TOPIC_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,34}$")
GITHUB_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_\.\-]+)/([a-zA-Z0-9_\.\-]+?)(?:\.git|/.*)?$"
)
SIMPLE_REPO_PATTERN = re.compile(r"^([a-zA-Z0-9_\.\-]+)/([a-zA-Z0-9_\.\-]+)$")


class AnalyzeRepoRequest(BaseModel):
    """Request payload to analyze a repository and generate descriptions."""

    repo_input: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="GitHub repository URL (e.g., https://github.com/owner/repo) or 'owner/repo'",
        examples=["octocat/Hello-World", "https://github.com/fastapi/fastapi"],
    )
    language: str = Field(
        default="ja",
        pattern=r"^(ja|en)$",
        description="Target language for the generated description ('ja' or 'en')",
    )
    tone: str = Field(
        default="concise",
        pattern=r"^(concise|catchy|technical)$",
        description="Tone of the description: concise (簡潔), catchy (魅力的), technical (技術的)",
    )
    target_char_limit: int = Field(
        default=350,
        ge=50,
        le=350,
        description="Maximum character length for GitHub description (hard limit: 350)",
    )

    @field_validator("repo_input")
    @classmethod
    def validate_and_normalize_repo(cls, v: str) -> str:
        clean_input = v.strip().strip("/")
        # Check standard URL
        match_url = GITHUB_URL_PATTERN.match(clean_input)
        if match_url:
            owner, repo = match_url.group(1), match_url.group(2)
            return f"{owner}/{repo}"

        # Check owner/repo format
        match_simple = SIMPLE_REPO_PATTERN.match(clean_input)
        if match_simple:
            owner, repo = match_simple.group(1), match_simple.group(2)
            if owner in (".", "..") or repo in (".", ".."):
                raise ValueError("無効なリポジトリ形式です（パストラバーサル禁止）。")
            return f"{owner}/{repo}"

        raise ValueError(
            "リポジトリ指定の形式が不正です。「owner/repo」または「https://github.com/owner/repo」を入力してください。"
        )


class RepoMetadata(BaseModel):
    """Extracted GitHub repository metadata."""

    owner: str
    repo: str
    full_name: str
    description: Optional[str] = None
    language: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    default_branch: str = "main"
    has_readme: bool = False
    html_url: str


class DescriptionVariant(BaseModel):
    """Generated description variant with tone and length."""

    tone: str
    description: str
    char_count: int


class AnalyzeRepoResponse(BaseModel):
    """Response returned after repository analysis."""

    success: bool = True
    metadata: RepoMetadata
    suggested_description: str
    char_count: int
    suggested_topics: List[str] = Field(default_factory=list)
    alternative_descriptions: List[DescriptionVariant] = Field(default_factory=list)
    engine_used: str  # "gemini" | "openai" | "heuristic"


class UpdateRepoDescriptionRequest(BaseModel):
    """Request payload to directly update a GitHub repository description."""

    owner: str = Field(..., min_length=1, max_length=100)
    repo: str = Field(..., min_length=1, max_length=100)
    description: str = Field(
        ...,
        min_length=1,
        max_length=350,
        description="New repository description (GitHub allows up to 350 chars)",
    )
    topics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of topics to update alongside description",
    )
    github_token: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=255,
        description="GitHub Personal Access Token (can also be supplied via X-GitHub-Token header)",
    )

    @field_validator("owner", "repo")
    @classmethod
    def validate_names(cls, v: str) -> str:
        v = v.strip()
        if not GITHUB_NAME_PATTERN.match(v) or v in (".", ".."):
            raise ValueError(f"無効なGitHub名フォーマットです: {v}")
        return v

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, topics: Optional[List[str]]) -> Optional[List[str]]:
        if topics is None:
            return None
        validated = []
        for t in topics:
            clean = t.strip().lower()
            if clean and GITHUB_TOPIC_PATTERN.match(clean):
                validated.append(clean)
        return validated[:20]  # GitHub allows max 20 topics


class UpdateRepoDescriptionResponse(BaseModel):
    """Response returned after updating repository description."""

    success: bool
    message: str
    current_description: str
    current_topics: List[str] = Field(default_factory=list)
    repo_url: str


class ErrorResponse(BaseModel):
    """Unified error response schema."""

    success: bool = False
    error: str
    error_id: Optional[str] = None
    detail: Optional[str] = None
