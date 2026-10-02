"""AI description generation service with Gemini, OpenAI, and smart heuristic fallback."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.schemas import DescriptionVariant

logger = logging.getLogger("github_description_app.ai")


class AIService:
    """Service to generate repository descriptions and topics via LLM or Heuristics."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-2.5-flash",
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
    ):
        self.gemini_key = gemini_api_key.strip() if gemini_api_key else None
        self.gemini_model = gemini_model
        self.openai_key = openai_api_key.strip() if openai_api_key else None
        self.openai_model = openai_model

    async def generate(
        self,
        repo_name: str,
        owner: str,
        current_description: Optional[str],
        primary_language: Optional[str],
        topics: List[str],
        readme_content: Optional[str],
        root_files: List[str],
        target_language: str = "ja",
        requested_tone: str = "concise",
        max_chars: int = 350,
    ) -> Dict[str, Any]:
        """
        Generate description and topics using best available engine.
        Falls back to Heuristic engine if LLM keys are absent or requests fail.
        """
        # Step 1: Pre-process README to save tokens & cost
        cleaned_readme = self._extract_readme_summary(readme_content)

        # Step 2: Try Gemini if key is provided
        if self.gemini_key:
            try:
                result = await self._call_gemini(
                    repo_name=repo_name,
                    owner=owner,
                    current_desc=current_description,
                    language=primary_language,
                    topics=topics,
                    readme_summary=cleaned_readme,
                    root_files=root_files,
                    target_language=target_language,
                    requested_tone=requested_tone,
                    max_chars=max_chars,
                )
                if result:
                    result["engine_used"] = "gemini"
                    return result
            except Exception as e:
                logger.warning("Gemini API call failed, attempting fallback: %s", type(e).__name__)

        # Step 3: Try OpenAI if key is provided
        if self.openai_key:
            try:
                result = await self._call_openai(
                    repo_name=repo_name,
                    owner=owner,
                    current_desc=current_description,
                    language=primary_language,
                    topics=topics,
                    readme_summary=cleaned_readme,
                    root_files=root_files,
                    target_language=target_language,
                    requested_tone=requested_tone,
                    max_chars=max_chars,
                )
                if result:
                    result["engine_used"] = "openai"
                    return result
            except Exception as e:
                logger.warning("OpenAI API call failed, attempting fallback: %s", type(e).__name__)

        # Step 4: Fallback to smart heuristic generator (0 cost, highly robust)
        logger.info("Using smart heuristic generation engine.")
        heuristic_result = self._generate_heuristic(
            repo_name=repo_name,
            owner=owner,
            current_desc=current_description,
            language=primary_language,
            topics=topics,
            readme_content=readme_content,
            root_files=root_files,
            target_language=target_language,
            requested_tone=requested_tone,
            max_chars=max_chars,
        )
        heuristic_result["engine_used"] = "heuristic"
        return heuristic_result

    def _extract_readme_summary(self, readme: Optional[str]) -> str:
        """Extract high-value sections of README while trimming boilerplate (max ~2500 chars)."""
        if not readme:
            return ""

        # Remove image links, badges, html comments
        cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", readme)
        cleaned = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", cleaned)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        selected_lines = []
        char_count = 0

        for line in lines:
            if char_count + len(line) > 2500:
                break
            selected_lines.append(line)
            char_count += len(line) + 1

        return "\n".join(selected_lines)

    async def _call_gemini(
        self,
        repo_name: str,
        owner: str,
        current_desc: Optional[str],
        language: Optional[str],
        topics: List[str],
        readme_summary: str,
        root_files: List[str],
        target_language: str,
        requested_tone: str,
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Call Google Gemini REST API."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_key}"
        )
        prompt = self._build_prompt(
            repo_name,
            owner,
            current_desc,
            language,
            topics,
            readme_summary,
            root_files,
            target_language,
            max_chars,
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning("Gemini error status %d", resp.status_code)
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return self._parse_json_response(content_text, requested_tone, max_chars)

    async def _call_openai(
        self,
        repo_name: str,
        owner: str,
        current_desc: Optional[str],
        language: Optional[str],
        topics: List[str],
        readme_summary: str,
        root_files: List[str],
        target_language: str,
        requested_tone: str,
        max_chars: int,
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI chat completions API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        prompt = self._build_prompt(
            repo_name,
            owner,
            current_desc,
            language,
            topics,
            readme_summary,
            root_files,
            target_language,
            max_chars,
        )

        payload = {
            "model": self.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert developer marketing assistant "
                               "specializing in GitHub repository descriptions.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning("OpenAI error status %d", resp.status_code)
                return None

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None

            content_text = choices[0].get("message", {}).get("content", "")
            return self._parse_json_response(content_text, requested_tone, max_chars)

    def _build_prompt(
        self,
        repo_name: str,
        owner: str,
        current_desc: Optional[str],
        language: Optional[str],
        topics: List[str],
        readme_summary: str,
        root_files: List[str],
        target_language: str,
        max_chars: int,
    ) -> str:
        lang_instruction = "日本語 (Japanese)" if target_language == "ja" else "English"
        return f"""
Analyze this GitHub repository and output descriptions and topics in {lang_instruction}.
GitHub limits repository descriptions to a MAXIMUM of 350 characters.

[Repository Info]
- Name: {owner}/{repo_name}
- Current Description: {current_desc or 'None'}
- Primary Language: {language or 'Unknown'}
- Existing Topics: {', '.join(topics) if topics else 'None'}
- Key Files: {', '.join(root_files[:15]) if root_files else 'None'}

[README Summary]
{readme_summary or 'No README provided.'}

[Requirements]
1. Output MUST be valid JSON adhering strictly to this JSON schema:
{{
  "concise": "A short, crystal-clear 1-2 sentence description (under {max_chars} chars)",
  "catchy": "A compelling, benefits-oriented description (under {max_chars} chars)",
  "technical": "A technical description detailing stack and purpose (under {max_chars} chars)",
  "topics": ["5 to 8 lowercase-hyphenated-topics-without-spaces-or-symbols"]
}}
2. All descriptions must be in {lang_instruction}.
3. Every description string MUST BE STRICTLY UNDER {max_chars} CHARACTERS.
4. The topics must only contain lowercase alphanumeric characters and hyphens.
"""

    def _parse_json_response(
        self, text: str, requested_tone: str, max_chars: int
    ) -> Dict[str, Any]:
        """Parse LLM JSON response and enforce defensive constraints."""
        text = text.strip()
        # Remove any markdown code fences if LLM wrapped it
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)

        data = json.loads(text)

        def sanitize_desc(desc_text: Optional[str]) -> str:
            if not desc_text:
                return ""
            desc = desc_text.strip()
            if len(desc) > max_chars:
                truncated = desc[:max_chars]
                last_punct = max(truncated.rfind("。"), truncated.rfind(". "), truncated.rfind(" "))
                if last_punct > max_chars // 2:
                    desc = truncated[:last_punct + (1 if truncated[last_punct] == "。" else 0)]
                else:
                    desc = truncated
            return desc.strip()

        concise = sanitize_desc(data.get("concise", ""))
        catchy = sanitize_desc(data.get("catchy", ""))
        technical = sanitize_desc(data.get("technical", ""))

        variants = [
            DescriptionVariant(tone="concise", description=concise, char_count=len(concise)),
            DescriptionVariant(tone="catchy", description=catchy, char_count=len(catchy)),
            DescriptionVariant(tone="technical", description=technical, char_count=len(technical)),
        ]

        # Select requested tone as primary
        selected_desc = concise
        if requested_tone == "catchy" and catchy:
            selected_desc = catchy
        elif requested_tone == "technical" and technical:
            selected_desc = technical
        elif not selected_desc:
            selected_desc = catchy or technical or "GitHubリポジトリの説明文"

        raw_topics = data.get("topics", [])
        cleaned_topics = []
        for t in raw_topics:
            clean = re.sub(r"[^a-z0-9\-]", "", str(t).lower().replace(" ", "-")).strip("-")
            if clean and clean not in cleaned_topics:
                cleaned_topics.append(clean)

        return {
            "suggested_description": selected_desc,
            "char_count": len(selected_desc),
            "suggested_topics": cleaned_topics[:10],
            "alternative_descriptions": variants,
        }

    def _generate_heuristic(
        self,
        repo_name: str,
        owner: str,
        current_desc: Optional[str],
        language: Optional[str],
        topics: List[str],
        readme_content: Optional[str],
        root_files: List[str],
        target_language: str,
        requested_tone: str,
        max_chars: int,
    ) -> Dict[str, Any]:
        """
        Rule-based heuristic generation engine.
        Parses README headers, detects technology from filenames, and formats descriptions.
        """
        tech_stack = []
        if language:
            tech_stack.append(language)

        file_lower = [f.lower() for f in root_files]
        if "dockerfile" in file_lower or "docker-compose.yml" in file_lower:
            tech_stack.append("Docker")
        if "package.json" in file_lower:
            tech_stack.append("Node.js")
        if "pyproject.toml" in file_lower or "requirements.txt" in file_lower:
            tech_stack.append("Python")
        if "cargo.toml" in file_lower:
            tech_stack.append("Rust")
        if "go.mod" in file_lower:
            tech_stack.append("Go")

        extracted_summary = ""
        if readme_content:
            lines = [line.strip() for line in readme_content.splitlines() if line.strip()]
            for line in lines:
                if line.startswith("#") or line.startswith("!") or line.startswith("[!["):
                    continue
                if len(line) > 20:
                    extracted_summary = line
                    break

        if not extracted_summary and current_desc:
            extracted_summary = current_desc

        stack_str = "/".join(dict.fromkeys(tech_stack)) if tech_stack else (language or "ソフト")

        if target_language == "ja":
            base_s = extracted_summary or f"{repo_name} の実装プロジェクト"
            concise = f"{repo_name} - {stack_str}を採用したリポジトリ。{base_s}"
            catchy = f"🚀 {repo_name}: {stack_str}で構築された信頼性の高いツール。{base_s}"
            technical = f"{repo_name} - {stack_str}ベース。{base_s} アーキテクチャを提供。"
        else:
            base_s = extracted_summary or f"Project repository for {repo_name}."
            concise = f"{repo_name} - Built with {stack_str}. {base_s}"
            catchy = f"🚀 {repo_name}: Powerful tool engineered with {stack_str}. {base_s}"
            technical = f"{repo_name} - Robust {stack_str} implementation. {base_s}"

        def trim(s: str) -> str:
            s = s.strip()
            if len(s) > max_chars:
                return s[: max_chars - 3] + "..."
            return s

        concise = trim(concise)
        catchy = trim(catchy)
        technical = trim(technical)

        variants = [
            DescriptionVariant(tone="concise", description=concise, char_count=len(concise)),
            DescriptionVariant(tone="catchy", description=catchy, char_count=len(catchy)),
            DescriptionVariant(tone="technical", description=technical, char_count=len(technical)),
        ]

        selected = concise
        if requested_tone == "catchy":
            selected = catchy
        elif requested_tone == "technical":
            selected = technical

        suggested_topics = list(dict.fromkeys(
            [t.lower() for t in topics] +
            [tech.lower() for tech in tech_stack] +
            ["developer-tools", "github", repo_name.lower().replace("_", "-")]
        ))

        valid_topics = [
            re.sub(r"[^a-z0-9\-]", "", t)
            for t in suggested_topics
            if t and re.match(r"^[a-z0-9\-]+$", t)
        ]

        return {
            "suggested_description": selected,
            "char_count": len(selected),
            "suggested_topics": valid_topics[:8],
            "alternative_descriptions": variants,
        }
