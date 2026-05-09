"""Ghibli-style recipe image generation via Google Imagen."""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from .common import load_dotenv_once

MODEL = "imagen-4.0-fast-generate-001"

MAX_RETRIES = 3

PROMPT_TEMPLATE = (
    "Fotografía gastronómica en primer plano de {dish}, "
    "presentado en un plato de cerámica rústica. "
    "Pintado en estilo Studio Ghibli con acuarela anime suave, iluminación cálida dorada y colores vibrantes y apetitosos. "
    "El foco está completamente en la comida — sin personas, sin personajes, sin animales, sin paisajes. "
    "Texturas detalladas, vapor ascendiendo, fondo de cocina acogedora desenfocado. "
    "Sin texto ni letras."
)


class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or is unavailable."""


class RateLimitError(ImageGenerationError):
    """Raised when rate limit is exhausted after retries."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _get_api_key() -> str:
    load_dotenv_once()
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ImageGenerationError(
            "Image generation unavailable: no Google API key configured "
            "(set GOOGLE_API_KEY or GEMINI_API_KEY)"
        )
    return key


def _build_prompt(title: str, subtitle: str | None = None) -> str:
    dish = title
    if subtitle:
        dish = f"{title} ({subtitle})"
    return PROMPT_TEMPLATE.format(dish=dish)


def _is_daily_quota(exc: ClientError) -> bool:
    """Check if the error is a daily quota exhaustion (not a transient rate limit)."""
    return "per_day" in str(exc).lower() or "RESOURCE_EXHAUSTED" == getattr(exc, "status", "")


def _parse_retry_seconds(exc: ClientError) -> int | None:
    """Extract retry delay in seconds from a Google API 429 error."""
    import re
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc), re.IGNORECASE)
    return int(float(match.group(1))) + 1 if match else None


def _call_api(client: genai.Client, prompt: str) -> bytes:
    """Call Imagen API with retry on 429 rate-limit errors."""
    last_exc: ClientError | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_images(
                model=MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                ),
            )
        except ClientError as e:
            if e.code == 429:
                # Daily quota → don't retry, fail immediately
                if _is_daily_quota(e):
                    raise RateLimitError(
                        "Límite diario de generación de imágenes alcanzado. "
                        "Inténtalo mañana.",
                    ) from e
                # Per-minute rate limit → retry with backoff
                if attempt < MAX_RETRIES:
                    wait = 3 + attempt * 2  # 3s, 5s, 7s
                    time.sleep(wait)
                    last_exc = e
                    continue
                last_exc = e
                break
            raise ImageGenerationError(f"Image generation failed: {e}") from e
        except Exception as e:
            raise ImageGenerationError(f"Image generation failed: {e}") from e

        if not response.generated_images:
            raise ImageGenerationError("Imagen returned no images")

        image_bytes = response.generated_images[0].image.image_bytes
        if not image_bytes:
            raise ImageGenerationError("Imagen returned empty image data")

        return image_bytes

    retry_after = _parse_retry_seconds(last_exc) if last_exc else None
    raise RateLimitError(
        "Límite de generación alcanzado. Espera un momento antes de reintentar.",
        retry_after=retry_after,
    )


def generate_recipe_image(title: str, subtitle: str | None = None) -> bytes:
    """Generate a Ghibli-style PNG image for a recipe.

    Returns raw PNG bytes. Retries on rate-limit (429) errors.
    Raises ImageGenerationError on failure.
    """
    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(title, subtitle)
    return _call_api(client, prompt)
