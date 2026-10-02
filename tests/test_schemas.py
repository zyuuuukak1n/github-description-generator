"""Unit tests for defensive schema validation, boundary values, and security injection attempts."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalyzeRepoRequest,
    UpdateRepoDescriptionRequest,
)


class TestAnalyzeRepoRequestValidation:
    """Tests for repository input validation, SSRF/traversal prevention, and edge cases."""

    def test_valid_short_format(self):
        req = AnalyzeRepoRequest(repo_input="fastapi/fastapi")
        assert req.repo_input == "fastapi/fastapi"

    def test_valid_full_https_url(self):
        req = AnalyzeRepoRequest(repo_input="https://github.com/octocat/Hello-World")
        assert req.repo_input == "octocat/Hello-World"

    def test_valid_url_with_git_extension(self):
        req = AnalyzeRepoRequest(repo_input="https://github.com/owner/repo.git")
        assert req.repo_input == "owner/repo"

    def test_valid_url_with_trailing_slash_and_subpath(self):
        req = AnalyzeRepoRequest(repo_input="https://github.com/owner/repo/tree/main")
        assert req.repo_input == "owner/repo"

    # Security: Path traversal injection attempts
    @pytest.mark.parametrize(
        "bad_input",
        [
            "../etc/passwd",
            "../../owner/repo",
            "owner/..",
            "./.",
            "owner/",
            "/repo",
            "http://evil.com/fake/repo",
            "https://notgithub.com/owner/repo",
            "owner/repo; rm -rf /",
            "owner/<script>alert(1)</script>",
            "owner/repo name with spaces",
            "owner//repo",
        ],
    )
    def test_invalid_and_malicious_inputs_rejected(self, bad_input: str):
        with pytest.raises(ValidationError):
            AnalyzeRepoRequest(repo_input=bad_input)

    # Boundary Value Tests for char limits
    def test_char_limit_boundary_values(self):
        # Minimum allowed limit (50)
        req_min = AnalyzeRepoRequest(repo_input="a/b", target_char_limit=50)
        assert req_min.target_char_limit == 50

        # Maximum allowed limit (350)
        req_max = AnalyzeRepoRequest(repo_input="a/b", target_char_limit=350)
        assert req_max.target_char_limit == 350

        # Below boundary
        with pytest.raises(ValidationError):
            AnalyzeRepoRequest(repo_input="a/b", target_char_limit=49)

        # Above boundary (exceeding GitHub limit of 350)
        with pytest.raises(ValidationError):
            AnalyzeRepoRequest(repo_input="a/b", target_char_limit=351)


class TestUpdateRepoDescriptionRequestValidation:
    """Tests for update payload validation, GitHub name constraints, and topic rules."""

    def test_valid_update_payload(self):
        req = UpdateRepoDescriptionRequest(
            owner="octocat",
            repo="Hello-World",
            description="A minimal hello world project",
            topics=["python", "fastapi", "open-source"],
            github_token="ghp_123456789012345678901234567890123456",
        )
        assert req.owner == "octocat"
        assert req.description == "A minimal hello world project"
        assert len(req.topics) == 3

    # Boundary: Exactly 350 chars allowed, 351 disallowed
    def test_description_length_boundary(self):
        exact_350 = "A" * 350
        req = UpdateRepoDescriptionRequest(
            owner="owner", repo="repo", description=exact_350
        )
        assert len(req.description) == 350

        exceed_351 = "A" * 351
        with pytest.raises(ValidationError):
            UpdateRepoDescriptionRequest(
                owner="owner", repo="repo", description=exceed_351
            )

        empty_desc = ""
        with pytest.raises(ValidationError):
            UpdateRepoDescriptionRequest(
                owner="owner", repo="repo", description=empty_desc
            )

    # Security: Name injection and path traversal
    @pytest.mark.parametrize("bad_name", ["..", ".", "owner/extra", "owner;rm", "owner space"])
    def test_malicious_owner_or_repo_rejected(self, bad_name: str):
        with pytest.raises(ValidationError):
            UpdateRepoDescriptionRequest(
                owner=bad_name, repo="valid-repo", description="test"
            )
        with pytest.raises(ValidationError):
            UpdateRepoDescriptionRequest(
                owner="valid-owner", repo=bad_name, description="test"
            )

    # Topics validation: normalization and rejection of invalid characters
    def test_topics_sanitization(self):
        req = UpdateRepoDescriptionRequest(
            owner="owner",
            repo="repo",
            description="test",
            topics=["Python", "Fast-API", "bad topic with space", "a" * 40, "valid-123"],
        )
        # Invalid topic with space & >35 chars should be omitted, valid ones normalized to lower
        assert "python" in req.topics
        assert "fast-api" in req.topics
        assert "valid-123" in req.topics
        assert "bad topic with space" not in req.topics
