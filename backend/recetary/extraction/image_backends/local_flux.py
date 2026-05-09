"""Local FLUX Schnell backend — calls a separate microservice."""
from __future__ import annotations

import os

import httpx

from ..common import load_dotenv_once
from ..imagen import ImageGenerationError

DEFAULT_URL = "http://localhost:8500"
TIMEOUT = 120  # local generation can take 15s+; generous timeout


def _get_url() -> str:
    load_dotenv_once()
    return os.environ.get("LOCAL_FLUX_URL", DEFAULT_URL)


def generate(prompt: str) -> bytes:
    """Generate an image via the local FLUX server. Returns PNG bytes."""
    url = _get_url()

    try:
        resp = httpx.post(
            f"{url}/generate",
            json={"prompt": prompt, "width": 1024, "height": 768},
            timeout=TIMEOUT,
        )
    except httpx.ConnectError as e:
        raise ImageGenerationError(
            f"Local FLUX server not reachable at {url}. "
            "Is flux_server.py running?"
        ) from e
    except httpx.TimeoutException as e:
        raise ImageGenerationError("Local FLUX generation timed out") from e

    if resp.status_code != 200:
        raise ImageGenerationError(
            f"Local FLUX error ({resp.status_code}): {resp.text[:200]}"
        )

    return resp.content
