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
    "Pintado en estilo acuarela anime suave con iluminación cálida dorada y colores vibrantes y apetitosos. "
    "El foco está completamente en la comida — sin personas, sin personajes, sin animales, sin paisajes. "
    "Texturas detalladas, vapor ascendiendo, fondo de cocina acogedora desenfocado. "
    "Sin texto ni letras."
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


def _build_prompt(title: str, subtitle: str | None = None) -> str:
    dish = title
    if subtitle:
        dish = f"{title} ({subtitle})"
    return PROMPT_TEMPLATE.format(dish=dish)


def _call_api(client: genai.Client, prompt: str) -> bytes:
    """Call Imagen API with retry on 429 rate-limit errors."""
    last_exc: Exception | None = None

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
            if e.status_code == 429 and attempt < MAX_RETRIES:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                time.sleep(wait)
                last_exc = e
                continue
            raise ImageGenerationError(f"Image generation failed: {e}") from e
        except Exception as e:
            raise ImageGenerationError(f"Image generation failed: {e}") from e

        if not response.generated_images:
            raise ImageGenerationError("Imagen returned no images")

        image_bytes = response.generated_images[0].image.image_bytes
        if not image_bytes:
            raise ImageGenerationError("Imagen returned empty image data")

        return image_bytes

    raise ImageGenerationError(
        f"Image generation failed after {MAX_RETRIES} retries: {last_exc}"
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
