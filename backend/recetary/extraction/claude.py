"""Claude-powered structured recipe extraction.

The extractor accepts any combination of PDF / image / text content and
returns a `RecipeDraft` validated against a Pydantic schema via forced
tool use.  The caller converts the draft into a `RecipeCreate` by
attaching source metadata.
"""
from __future__ import annotations

import base64
from typing import Iterable, Optional

import anthropic

from .common import (
    SYSTEM_INSTRUCTIONS,
    ExtractionError,
    RecipeDraft,
    build_canonical_preamble,
    load_dotenv_once,
)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096


class ClaudeExtractor:
    def __init__(self, *, model: str = DEFAULT_MODEL) -> None:
        load_dotenv_once()
        self.client = anthropic.Anthropic()
        self.model = model

    def _system(self) -> list[dict]:
        return [
            {
                "type": "text",
                "text": SYSTEM_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _build_user_content(
        self,
        *,
        canonical_ingredients: Iterable[str],
        text: Optional[str],
        pdf_bytes: Optional[bytes],
        image_bytes: Optional[bytes],
        image_media_type: Optional[str],
        source_hint: Optional[str],
    ) -> list[dict]:
        preamble = build_canonical_preamble(canonical_ingredients)
        content: list[dict] = [{"type": "text", "text": preamble}]

        if pdf_bytes is not None:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                    },
                }
            )
        if image_bytes is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type or "image/jpeg",
                        "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                    },
                }
            )
        if text:
            content.append(
                {"type": "text", "text": f"Recipe text:\n\n{text.strip()}"}
            )

        prompt = "Extract the recipe from the source above into the structured schema."
        if source_hint:
            prompt += f"\n\nSource hint: {source_hint}"
        content.append({"type": "text", "text": prompt})
        return content

    def _tool_definition(self) -> dict:
        """Build the single tool that forces the model to emit a RecipeDraft."""
        schema = RecipeDraft.model_json_schema()
        return {
            "name": "submit_recipe",
            "description": "Submit the structured recipe extracted from the source.",
            "input_schema": schema,
        }

    def extract(
        self,
        *,
        canonical_ingredients: Iterable[str] = (),
        text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        image_bytes: Optional[bytes] = None,
        image_media_type: Optional[str] = None,
        source_hint: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> RecipeDraft:
        if not any((text, pdf_bytes, image_bytes)):
            raise ValueError("extract() requires at least one of text, pdf_bytes, image_bytes")

        user_content = self._build_user_content(
            canonical_ingredients=canonical_ingredients,
            text=text,
            pdf_bytes=pdf_bytes,
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            source_hint=source_hint,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(),
            tools=[self._tool_definition()],
            tool_choice={"type": "tool", "name": "submit_recipe"},
            messages=[{"role": "user", "content": user_content}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_recipe":
                return RecipeDraft.model_validate(block.input)

        raise ExtractionError(
            f"Claude returned no submit_recipe tool call (stop_reason={response.stop_reason!r})"
        )
