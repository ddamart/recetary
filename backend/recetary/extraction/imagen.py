"""Ghibli-style recipe image generation via Google Imagen."""
from __future__ import annotations

import os

from google import genai
from google.genai import types

from .common import load_dotenv_once

MODEL = "imagen-4.0-fast-generate-001"

STYLE_PREFIX = "A warm Studio Ghibli-style watercolor food illustration of"
STYLE_SUFFIX = (
    "hand-painted with soft cel-shading, warm golden lighting, "
    "beautifully plated on a rustic wooden table. "
    "Cozy kitchen atmosphere inspired by Hayao Miyazaki films. "
    "Detailed, appetizing, vibrant colors, no text or lettering."
)


class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or is unavailable."""


def _get_api_key() -> str:
    load_dotenv_once()
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ImageGenerationError(
            "Image generation unavailable: no Google API key configured "
            "(set GOOGLE_API_KEY or GEMINI_API_KEY)"
        )
    return key


def _build_prompt(title: str, description: str | None = None) -> str:
    dish = title
    if description:
        dish = f"{title} — {description}"
    return f"{STYLE_PREFIX} {dish}. {STYLE_SUFFIX}"


def generate_recipe_image(title: str, description: str | None = None) -> bytes:
    """Generate a Ghibli-style PNG image for a recipe.

    Returns raw PNG bytes. Raises ImageGenerationError on failure.
    """
    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(title, description)

    try:
        response = client.models.generate_images(
            model=MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
            ),
        )
    except Exception as e:
        raise ImageGenerationError(f"Image generation failed: {e}") from e

    if not response.generated_images:
        raise ImageGenerationError("Imagen returned no images")

    image_bytes = response.generated_images[0].image.image_bytes
    if not image_bytes:
        raise ImageGenerationError("Imagen returned empty image data")

    return image_bytes
