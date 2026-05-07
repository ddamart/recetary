"""Recipe extraction backends (Claude / Gemini).

The active backend is chosen by the EXTRACTOR_BACKEND env var:
  - "claude" (default) → Anthropic Claude Sonnet via tool use
  - "gemini"           → Google Gemini Flash via JSON schema mode
"""
from __future__ import annotations

import os

from .common import ExtractionError, RecipeDraft, draft_to_create, load_dotenv_once

__all__ = [
    "ExtractionError",
    "RecipeDraft",
    "draft_to_create",
    "get_extractor",
]


def get_extractor():
    """Return the configured extractor singleton."""
    load_dotenv_once()
    backend = os.environ.get("EXTRACTOR_BACKEND", "claude").lower()
    if backend == "gemini":
        from .gemini import GeminiExtractor

        return GeminiExtractor()
    from .claude import ClaudeExtractor

    return ClaudeExtractor()
