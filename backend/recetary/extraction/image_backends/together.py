"""Together AI image generation backend (FLUX Schnell)."""
from __future__ import annotations

import base64
import os

import httpx

from ..common import load_dotenv_once
from ..imagen import ImageGenerationError, RateLimitError

TOGETHER_MODEL = "black-forest-labs/FLUX.1-schnell"
TOGETHER_URL = "https://api.together.ai/v1/images/generations"
TIMEOUT = 60


def _get_api_key() -> str:
    load_dotenv_once()
    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise ImageGenerationError(
            "Together AI unavailable: set TOGETHER_API_KEY"
        )
    return key


def generate(prompt: str) -> bytes:
    """Generate an image via Together AI FLUX Schnell. Returns PNG bytes."""
    api_key = _get_api_key()

    try:
        resp = httpx.post(
            TOGETHER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": TOGETHER_MODEL,
                "prompt": prompt,
                "steps": 4,
                "width": 1024,
                "height": 768,
                "n": 1,
                "response_format": "b64_json",
            },
            timeout=TIMEOUT,
        )
    except httpx.TimeoutException as e:
        raise ImageGenerationError("Together AI request timed out") from e
    except httpx.ConnectError as e:
        raise ImageGenerationError(f"Together AI connection failed: {e}") from e

    if resp.status_code == 429:
        raise RateLimitError(
            "Límite de generación alcanzado en Together AI. "
            "Espera un momento antes de reintentar.",
        )
    if resp.status_code != 200:
        raise ImageGenerationError(
            f"Together AI error ({resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    try:
        b64 = data["data"][0]["b64_json"]
        return base64.b64decode(b64)
    except (KeyError, IndexError) as e:
        raise ImageGenerationError("Together AI returned unexpected response") from e
