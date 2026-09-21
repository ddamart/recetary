"""Together AI image generation backend."""
from __future__ import annotations

import base64
import os

import httpx

from ..common import load_dotenv_once
from ..imagen import ImageGenerationError, RateLimitError

DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"
TOGETHER_URL = "https://api.together.ai/v1/images/generations"
TIMEOUT = 60


def _get_api_key() -> str:
    load_dotenv_once()
    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise ImageGenerationError("Together AI unavailable: set TOGETHER_API_KEY")
    return key


def generate(
    prompt: str,
    *,
    seed: int | None = None,
    width: int = 1024,
    height: int = 768,
    steps: int = 4,
) -> bytes:
    """Generate an image via Together AI. Returns PNG bytes."""
    api_key = _get_api_key()
    payload: dict[str, object] = {
        "model": os.environ.get("TOGETHER_MODEL", DEFAULT_MODEL),
        "prompt": prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "n": 1,
        "response_format": "b64_json",
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        resp = httpx.post(
            TOGETHER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
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

    try:
        return base64.b64decode(resp.json()["data"][0]["b64_json"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ImageGenerationError("Together AI returned unexpected response") from e
