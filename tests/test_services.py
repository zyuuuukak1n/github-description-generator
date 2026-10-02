"""Unit tests for AIService and GitHubService business logic."""

import pytest

from app.ai_service import AIService
from app.github_service import GitHubAPIError, GitHubService


@pytest.fixture
def ai_service():
    """Create AI service without external API keys (tests heuristic engine)."""
    return AIService()


class TestAIService:
    """Test AI and heuristic description generation logic."""

    @pytest.mark.asyncio
    async def test_heuristic_generation_with_readme(self, ai_service: AIService):
        readme_content = """# Awesome Project
[![Build](https://img.shields.io/badge/build-passing-green)](#)

Awesome Project is an ultra-fast developer tool designed to automate repository summaries.

## Features
- Fast indexing
- Multi-language support
"""
        result = await ai_service.generate(
            repo_name="awesome-tool",
            owner="developer",
            current_description=None,
            primary_language="Python",
            topics=["cli", "developer-tools"],
            readme_content=readme_content,
            root_files=["pyproject.toml", "Dockerfile", "README.md"],
            target_language="ja",
            requested_tone="concise",
            max_chars=350,
        )

        assert result["engine_used"] == "heuristic"
        assert result["suggested_description"]
        assert len(result["suggested_description"]) <= 350
        assert result["char_count"] <= 350
        assert len(result["alternative_descriptions"]) == 3
        # Ensure variants exist for each tone
        tones = [v.tone for v in result["alternative_descriptions"]]
        assert "concise" in tones
        assert "catchy" in tones
        assert "technical" in tones
        # Topics should include detected stack
        assert "python" in result["suggested_topics"]
        assert "docker" in result["suggested_topics"]

    @pytest.mark.asyncio
    async def test_heuristic_generation_empty_readme(self, ai_service: AIService):
        result = await ai_service.generate(
            repo_name="bare-repo",
            owner="developer",
            current_description="A minimal repo without readme",
            primary_language="Rust",
            topics=[],
            readme_content=None,
            root_files=["Cargo.toml"],
            target_language="ja",
            requested_tone="catchy",
            max_chars=200,
        )
        assert result["suggested_description"]
        assert len(result["suggested_description"]) <= 200
        assert "rust" in result["suggested_topics"]

    @pytest.mark.asyncio
    async def test_strict_length_boundary_enforcement(self, ai_service: AIService):
        # Extremely small limit test
        result = await ai_service.generate(
            repo_name="length-test",
            owner="tester",
            current_description="Some long current description text that needs truncation",
            primary_language="Go",
            topics=[],
            readme_content="Lots of text " * 100,
            root_files=[],
            target_language="en",
            requested_tone="concise",
            max_chars=80,
        )
        assert len(result["suggested_description"]) <= 80


class TestGitHubService:
    """Test GitHub API service error handling and defensive checks."""

    @pytest.mark.asyncio
    async def test_update_without_token_raises_401(self):
        service = GitHubService()
        with pytest.raises(GitHubAPIError) as exc_info:
            await service.update_repository_description(
                owner="test",
                repo="repo",
                description="desc",
                topics=None,
                token="",
            )
        assert exc_info.value.status_code == 401
        assert "Personal Access Token" in exc_info.value.message
