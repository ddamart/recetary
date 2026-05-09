"""Multi-style recipe image generation with pluggable backends.

Prompt building (Gemini translation + style frame) is shared by all backends.
The actual image generation is dispatched to the backend selected by the
``IMAGE_BACKEND`` env var: ``imagen`` (default), ``together``, or ``local``.
"""
from __future__ import annotations

import logging
import os
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from .common import load_dotenv_once

logger = logging.getLogger(__name__)

MODEL = "imagen-4.0-fast-generate-001"

MAX_RETRIES = 3

STYLES: dict[str, dict[str, str]] = {
    "ghibli": {
        "label": "Ghibli",
        "prompt": (
            "Painted in Studio Ghibli style with soft anime watercolor, "
            "warm golden lighting and vibrant appetizing colors."
        ),
    },
    "realistic": {
        "label": "Realista",
        "prompt": (
            "Professional food magazine photography with natural side lighting, "
            "shallow depth of field and vibrant natural colors."
        ),
    },
    "watercolor": {
        "label": "Acuarela clásica",
        "prompt": (
            "Traditional watercolor illustration on textured paper with loose "
            "visible brushstrokes, warm soft color palette, artisan cookbook style."
        ),
    },
    "popart": {
        "label": "Pop Art",
        "prompt": (
            "Pop art style with bold saturated flat colors, thick black comic-book "
            "outlines, Ben-Day dot patterns."
        ),
    },
    "minimal": {
        "label": "Minimalista",
        "prompt": (
            "Minimalist flat design with simplified geometric shapes, "
            "soft pastel colors and clean composition without textures."
        ),
    },
    "pixel": {
        "label": "Pixel Art",
        "prompt": (
            "Retro 16-bit pixel art style with visible pixels, "
            "limited vibrant color palette, like a classic video game."
        ),
    },
}

DEFAULT_STYLE = "ghibli"

PROMPT_FRAME = (
    "Close-up food photography of {dish}, "
    "served on a rustic ceramic plate. "
    "{style_prompt} "
    "Focus entirely on the food — no people, no characters, no animals. "
    "Detailed textures, steam rising, cozy blurred kitchen background. "
    "The image must NOT contain any text, letters, words, numbers, "
    "watermarks or typography of any kind."
)


class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or is unavailable."""


class RateLimitError(ImageGenerationError):
    """Raised when rate limit is exhausted after retries."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def get_available_styles() -> list[dict[str, str]]:
    """Return the list of available image styles as {id, label} dicts."""
    return [{"id": k, "label": v["label"]} for k, v in STYLES.items()]


TRANSLATE_MODEL = "gemini-2.5-flash"


def _get_api_key() -> str:
    load_dotenv_once()
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ImageGenerationError(
            "Image generation unavailable: no Google API key configured "
            "(set GOOGLE_API_KEY or GEMINI_API_KEY)"
        )
    return key


def _translate_dish(
    client: genai.Client,
    title: str,
    subtitle: str | None,
    description: str | None,
    reference_image_bytes: bytes | None = None,
    reference_mime_type: str | None = None,
) -> str:
    """Translate a Spanish dish to a concise English visual description.

    When a reference image is provided, Gemini analyses it for a more accurate
    description of the finished dish.
    """
    parts = [title]
    if subtitle:
        parts.append(subtitle)
    if description:
        parts.append(description)
    dish_text = " — ".join(parts)

    if reference_image_bytes and reference_mime_type:
        prompt_text = (
            "Look at this photo of the dish and the Spanish recipe info below. "
            f"Write a short English description (max 25 words) of what the finished "
            "dish looks like on a plate. Describe colors, textures, and plating. "
            "Use common English food terms an image generator would understand — "
            "avoid ambiguous foreign words. Reply ONLY with the description.\n\n"
            f"{dish_text}"
        )
        contents = [
            types.Part.from_bytes(data=reference_image_bytes, mime_type=reference_mime_type),
            prompt_text,
        ]
    else:
        contents = (
            "Given this Spanish recipe info, write a short English description "
            f"(max 25 words) of what the finished dish looks like on a plate. "
            "Describe colors, textures, and plating. Use common English food terms "
            "an image generator would understand — avoid ambiguous foreign words. "
            "Reply ONLY with the description.\n\n"
            f"{dish_text}"
        )

    try:
        response = client.models.generate_content(
            model=TRANSLATE_MODEL,
            contents=contents,
        )
        translated = response.text.strip()
        if translated:
            logger.info("Dish translation: %r -> %r", title, translated)
            return translated
        logger.warning("Gemini returned empty translation for %r, using title as-is", title)
        return title
    except Exception as exc:
        logger.warning("Dish translation failed for %r: %s — using title as-is", title, exc)
        return title


def _build_prompt(
    client: genai.Client,
    title: str,
    subtitle: str | None = None,
    description: str | None = None,
    style: str = DEFAULT_STYLE,
    reference_image_bytes: bytes | None = None,
    reference_mime_type: str | None = None,
) -> str:
    dish_en = _translate_dish(
        client, title, subtitle, description,
        reference_image_bytes, reference_mime_type,
    )
    style_prompt = STYLES.get(style, STYLES[DEFAULT_STYLE])["prompt"]
    return PROMPT_FRAME.format(dish=dish_en, style_prompt=style_prompt)


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


VALID_BACKENDS = {"imagen", "together", "local"}


def get_image_backend() -> str:
    """Return the active image backend name (for /info)."""
    load_dotenv_once()
    return os.environ.get("IMAGE_BACKEND", "imagen").lower()


def _call_backend(prompt: str) -> bytes:
    """Dispatch image generation to the configured backend."""
    backend = get_image_backend()

    if backend == "together":
        from .image_backends.together import generate
        return generate(prompt)

    if backend == "local":
        from .image_backends.local_flux import generate
        return generate(prompt)

    if backend == "imagen":
        api_key = _get_api_key()
        client = genai.Client(api_key=api_key)
        return _call_api(client, prompt)

    raise ImageGenerationError(
        f"Unknown IMAGE_BACKEND={backend!r}. "
        f"Valid options: {', '.join(sorted(VALID_BACKENDS))}"
    )


def generate_recipe_image(
    title: str,
    subtitle: str | None = None,
    description: str | None = None,
    style: str = DEFAULT_STYLE,
    reference_image_bytes: bytes | None = None,
    reference_mime_type: str | None = None,
) -> bytes:
    """Generate a styled PNG image for a recipe.

    When *reference_image_bytes* is provided, Gemini Flash analyses the photo
    to produce a more accurate visual description before passing it to Imagen.

    Returns raw PNG bytes. Retries on rate-limit (429) errors.
    Raises ImageGenerationError on failure.
    """
    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(
        client, title, subtitle, description, style,
        reference_image_bytes, reference_mime_type,
    )
    return _call_backend(prompt)
