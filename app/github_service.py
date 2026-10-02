"""GitHub REST API async service for fetching repo data and updating description."""

import base64
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.schemas import RepoMetadata

logger = logging.getLogger("github_description_app.github")
GITHUB_API_BASE = "https://api.github.com"
MAX_README_BYTES = 500 * 1024  # 500 KB defensive limit


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors with safe user messaging."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubService:
    """Service to interact securely with GitHub REST API."""

    def __init__(self, default_token: Optional[str] = None):
        self.default_token = default_token.strip() if default_token else None

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitHub-Description-Generator/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        active_token = token or self.default_token
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"
        return headers

    async def get_repository_details(
        self, owner: str, repo: str, token: Optional[str] = None
    ) -> RepoMetadata:
        """Fetch general repository metadata."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                logger.error("GitHub API connection error: %s", type(exc).__name__)
                raise GitHubAPIError(
                    "GitHub APIへの接続に失敗しました。時間をおいて再試行してください。", 502
                ) from exc

            if response.status_code == 404:
                raise GitHubAPIError(
                    f"リポジトリ '{owner}/{repo}' が見つかりません。設定をご確認ください。",
                    404,
                )
            elif response.status_code == 403:
                rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
                if rate_limit_remaining == "0":
                    raise GitHubAPIError(
                        "GitHub APIのレート制限に達しました。トークンを設定してください。",
                        429,
                    )
                raise GitHubAPIError("GitHub APIへのアクセス権限がありません(403)。", 403)
            elif response.status_code == 401:
                raise GitHubAPIError("GitHub認証トークンが無効または期限切れです(401)。", 401)
            elif response.status_code != 200:
                logger.error("Unexpected GitHub API response code: %d", response.status_code)
                raise GitHubAPIError(
                    "GitHubリポジトリ情報の取得に失敗しました。", response.status_code
                )

            data: Dict[str, Any] = response.json()
            return RepoMetadata(
                owner=owner,
                repo=repo,
                full_name=data.get("full_name", f"{owner}/{repo}"),
                description=data.get("description"),
                language=data.get("language"),
                topics=data.get("topics", []),
                stars=data.get("stargazers_count", 0),
                forks=data.get("forks_count", 0),
                default_branch=data.get("default_branch", "main"),
                has_readme=False,  # updated subsequently
                html_url=data.get("html_url", f"https://github.com/{owner}/{repo}"),
            )

    async def get_repository_readme(
        self, owner: str, repo: str, token: Optional[str] = None
    ) -> Optional[str]:
        """Fetch and decode the repository's README file if it exists."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                logger.warning(
                    "Failed to fetch README due to connection error: %s", type(exc).__name__
                )
                return None

            if response.status_code == 404:
                return None  # No README present
            elif response.status_code != 200:
                logger.warning("README fetch returned status code: %d", response.status_code)
                return None

            try:
                data = response.json()
                encoding = data.get("encoding", "base64")
                content = data.get("content", "")

                if encoding == "base64" and content:
                    raw_bytes = base64.b64decode(content)
                    if len(raw_bytes) > MAX_README_BYTES:
                        raw_bytes = raw_bytes[:MAX_README_BYTES]
                    return raw_bytes.decode("utf-8", errors="replace")
                return content
            except Exception as e:
                logger.warning("Error decoding README content: %s", type(e).__name__)
                return None

    async def get_repository_root_files(
        self, owner: str, repo: str, token: Optional[str] = None
    ) -> List[str]:
        """Fetch list of filenames in the root directory for technology stack detection."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
        headers = self._get_headers(token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return [item.get("name", "") for item in data if "name" in item][:40]
            except Exception as e:
                logger.warning("Failed to list root contents: %s", type(e).__name__)
        return []

    async def update_repository_description(
        self,
        owner: str,
        repo: str,
        description: str,
        topics: Optional[List[str]],
        token: str,
    ) -> Tuple[str, List[str]]:
        """
        Directly update GitHub repository description and topics using user's PAT.
        Returns updated (description, topics).
        """
        if not token or not token.strip():
            raise GitHubAPIError(
                "リポジトリの更新にはGitHub Personal Access Token (PAT) が必要です。", 401
            )

        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        headers = self._get_headers(token.strip())
        payload: Dict[str, Any] = {"description": description}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.patch(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                logger.error("GitHub API patch connection error: %s", type(exc).__name__)
                raise GitHubAPIError("GitHub APIへの接続に失敗しました。", 502) from exc

            if response.status_code == 401:
                raise GitHubAPIError(
                    "GitHub PATが無効か期限切れです。適切な権限を持つトークンを入力してください。",
                    401,
                )
            elif response.status_code in (403, 404):
                raise GitHubAPIError(
                    f"リポジトリ '{owner}/{repo}' への書き込み権限がありません。"
                    "トークン権限を確認してください。",
                    403,
                )
            elif response.status_code != 200:
                logger.error("Failed to update repo description. HTTP %d", response.status_code)
                raise GitHubAPIError(
                    f"リポジトリ説明文の更新に失敗しました (Status {response.status_code})。",
                    response.status_code,
                )

            data = response.json()
            updated_desc = data.get("description", description)
            current_topics = data.get("topics", [])

            # Update topics if requested
            if topics is not None:
                topics_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/topics"
                topics_payload = {"names": topics}
                try:
                    top_resp = await client.put(topics_url, headers=headers, json=topics_payload)
                    if top_resp.status_code == 200:
                        current_topics = top_resp.json().get("names", topics)
                    else:
                        logger.warning(
                            "Topics update status code: %d", top_resp.status_code
                        )
                except Exception as e:
                    logger.warning("Failed to update topics: %s", type(e).__name__)

            return updated_desc, current_topics
