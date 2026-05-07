"""Gemini-powered structured recipe extraction.

Uses the google-genai SDK with JSON-schema constrained output to mirror
the same RecipeDraft interface as the Claude backend.
"""
from __future__ import annotations

import json
import os
from typing import Iterable, Optional

from google import genai
from google.genai import types

from .common import (
    SYSTEM_INSTRUCTIONS,
    ExtractionError,
    RecipeDraft,
    build_canonical_preamble,
    load_dotenv_once,
)

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiExtractor:
    def __init__(self, *, model: str = DEFAULT_MODEL) -> None:
        load_dotenv_once()
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _build_contents(
        self,
        *,
        canonical_ingredients: Iterable[str],
        text: Optional[str],
        pdf_bytes: Optional[bytes],
        image_bytes: Optional[bytes],
        image_media_type: Optional[str],
        source_hint: Optional[str],
    ) -> list[types.Part]:
        preamble = build_canonical_preamble(canonical_ingredients)
        parts: list[types.Part] = [types.Part.from_text(text=preamble)]

        if pdf_bytes is not None:
            parts.append(
                types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf",
                )
            )
        if image_bytes is not None:
            parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=image_media_type or "image/jpeg",
                )
            )
        if text:
            parts.append(
                types.Part.from_text(text=f"Recipe text:\n\n{text.strip()}")
            )

        prompt = "Extract the recipe from the source above into the structured schema."
        if source_hint:
            prompt += f"\n\nSource hint: {source_hint}"
        parts.append(types.Part.from_text(text=prompt))
        return parts

    def _parse_response(self, response) -> RecipeDraft:
        if not response.text:
            raise ExtractionError(
                f"Gemini returned empty response (finish_reason={response.candidates[0].finish_reason!r})"
            )
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            raise ExtractionError(f"Gemini returned invalid JSON: {e}")
        return RecipeDraft.model_validate(data)

    def extract(
        self,
        *,
        canonical_ingredients: Iterable[str] = (),
        text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        image_bytes: Optional[bytes] = None,
        image_media_type: Optional[str] = None,
        source_hint: Optional[str] = None,
        max_tokens: int = 8192,
    ) -> RecipeDraft:
        if not any((text, pdf_bytes, image_bytes)):
            raise ValueError("extract() requires at least one of text, pdf_bytes, image_bytes")

        parts = self._build_contents(
            canonical_ingredients=canonical_ingredients,
            text=text,
            pdf_bytes=pdf_bytes,
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            source_hint=source_hint,
        )

        schema = RecipeDraft.model_json_schema()

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        return self._parse_response(response)

    def extract_video_url(
        self,
        *,
        video_url: str,
        transcript_text: Optional[str] = None,
        canonical_ingredients: Iterable[str] = (),
        max_tokens: int = 8192,
    ) -> RecipeDraft:
        """Extract a recipe directly from a YouTube video URL.

        Gemini can process YouTube videos natively via Part.from_uri(),
        seeing visual instructions and hearing spoken content.
        """
        preamble = build_canonical_preamble(canonical_ingredients)
        parts: list[types.Part] = [types.Part.from_text(text=preamble)]

        parts.append(types.Part.from_uri(uri=video_url, mime_type="video/*"))

        if transcript_text:
            parts.append(
                types.Part.from_text(
                    text=f"Video transcript (for reference):\n\n{transcript_text.strip()}"
                )
            )

        parts.append(
            types.Part.from_text(
                text="Extract the recipe from the video above into the structured schema."
            )
        )

        schema = RecipeDraft.model_json_schema()

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        return self._parse_response(response)

    def extract_video_bytes(
        self,
        *,
        video_bytes: bytes,
        video_mime_type: str = "video/mp4",
        supplementary_text: Optional[str] = None,
        canonical_ingredients: Iterable[str] = (),
        max_tokens: int = 8192,
    ) -> RecipeDraft:
        """Extract a recipe from raw video bytes (e.g. Twitter/X videos).

        Sends the video inline via Part.from_bytes() for Gemini to process
        the visual and audio content directly.
        """
        preamble = build_canonical_preamble(canonical_ingredients)
        parts: list[types.Part] = [types.Part.from_text(text=preamble)]

        parts.append(types.Part.from_bytes(data=video_bytes, mime_type=video_mime_type))

        if supplementary_text and supplementary_text.strip():
            parts.append(
                types.Part.from_text(
                    text=f"Additional context (tweet/post text):\n\n{supplementary_text.strip()}"
                )
            )

        parts.append(
            types.Part.from_text(
                text="Extract the recipe from the video above into the structured schema."
            )
        )

        schema = RecipeDraft.model_json_schema()

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        return self._parse_response(response)
