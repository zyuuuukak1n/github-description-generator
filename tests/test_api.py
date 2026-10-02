"""Integration and security test suite for FastAPI API endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.github_service import GitHubAPIError
from app.main import app
from app.schemas import RepoMetadata

client = TestClient(app)
client_safe = TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for health monitoring endpoint and security headers."""

    def test_health_check_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_security_headers_present(self):
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "X-Process-Time" in response.headers


class TestAnalyzeEndpoint:
    """Tests for POST /api/analyze."""

    @patch("app.main.github_service.get_repository_details")
    @patch("app.main.github_service.get_repository_readme")
    @patch("app.main.github_service.get_repository_root_files")
    def test_analyze_success_happy_path(self, mock_files, mock_readme, mock_details):
        mock_details.return_value = RepoMetadata(
            owner="octocat",
            repo="Hello-World",
            full_name="octocat/Hello-World",
            description="My first repo",
            language="Python",
            topics=["sample"],
            stars=100,
            forks=20,
            default_branch="main",
            has_readme=True,
            html_url="https://github.com/octocat/Hello-World",
        )
        mock_readme.return_value = "# Hello World\nSample python project"
        mock_files.return_value = ["README.md", "main.py"]

        response = client.post(
            "/api/analyze",
            json={
                "repo_input": "octocat/Hello-World",
                "language": "ja",
                "tone": "concise",
                "target_char_limit": 350,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["owner"] == "octocat"
        assert len(data["suggested_description"]) <= 350
        assert data["engine_used"] in ("gemini", "openai", "heuristic")

    def test_analyze_invalid_input_validation_error(self):
        # Malicious SSRF path traversal attempt
        response = client.post(
            "/api/analyze",
            json={"repo_input": "../../etc/passwd"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "入力値が無効です" in data["error"]

    @patch("app.main.github_service.get_repository_details")
    def test_analyze_repo_not_found(self, mock_details):
        mock_details.side_effect = GitHubAPIError(
            "リポジトリ 'ghost/missing' が見つかりません。", 404
        )
        response = client.post(
            "/api/analyze",
            json={"repo_input": "ghost/missing"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "見つかりません" in data["error"]


class TestUpdateEndpointAndSecurity:
    """Tests for POST /api/update including unauthorized and forbidden access attempts."""

    def test_update_missing_token_unauthorized(self):
        """Security: Unauthorized update attempt without token must be blocked (401)."""
        response = client.post(
            "/api/update",
            json={
                "owner": "octocat",
                "repo": "Hello-World",
                "description": "Updated description",
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "Personal Access Token" in data["error"]

    @patch("app.main.github_service.update_repository_description")
    def test_update_unauthorized_token_forbidden(self, mock_update):
        """Security: Token with insufficient permissions must yield 403."""
        mock_update.side_effect = GitHubAPIError(
            "リポジトリへの書き込み権限がありません(403)。", 403
        )
        response = client.post(
            "/api/update",
            headers={"X-GitHub-Token": "ghp_invalid_token_sample_1234567890"},
            json={
                "owner": "octocat",
                "repo": "Hello-World",
                "description": "Unauthorized attempt",
            },
        )
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert "書き込み権限がありません" in data["error"]

    @patch("app.main.github_service.update_repository_description")
    def test_update_success_happy_path(self, mock_update):
        """Happy Path: Successful description update with token in header."""
        mock_update.return_value = (
            "Updated successfully",
            ["python", "fastapi"],
        )
        response = client.post(
            "/api/update",
            headers={"X-GitHub-Token": "ghp_valid_token_sample_1234567890"},
            json={
                "owner": "octocat",
                "repo": "Hello-World",
                "description": "Updated successfully",
                "topics": ["python", "fastapi"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["current_description"] == "Updated successfully"
        # Security: Token should never be returned in response body
        assert "ghp_valid_token" not in str(data)

    def test_update_description_exceeding_350_rejected(self):
        """Boundary: Description > 350 chars must fail validation (422)."""
        response = client.post(
            "/api/update",
            headers={"X-GitHub-Token": "ghp_valid_token_sample_1234567890"},
            json={
                "owner": "octocat",
                "repo": "Hello-World",
                "description": "X" * 351,
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False


class TestUnhandledExceptionMasking:
    """Defensive: Ensure 500 exceptions do not leak stack traces or internals."""

    @patch("app.main.github_service.get_repository_details")
    def test_internal_error_masks_details(self, mock_details):
        # Simulate unexpected crash (e.g. database/OS crash)
        mock_details.side_effect = RuntimeError("CRITICAL DATABASE CORRUPTION SECRET_KEY=12345")

        response = client_safe.post(
            "/api/analyze",
            json={"repo_input": "octocat/Hello-World"},
        )
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        # Sensitive internal message MUST NOT be leaked
        assert "SECRET_KEY" not in str(data)
        assert "CRITICAL DATABASE" not in str(data)
        assert "内部で予期せぬエラーが発生しました" in data["error"]
        assert "error_id" in data
        assert data["error_id"]  # UUID exists for operational tracking
