"""Local FLUX Schnell backend — calls a separate microservice."""
from __future__ import annotations

import os

import httpx

from ..common import load_dotenv_once
from ..imagen import ImageGenerationError

DEFAULT_URL = "http://localhost:8500"
TIMEOUT = 180  # LoRA load + generation can take longer; generous timeout
DEFAULT_STEPS = 8  # schnell: quality improves meaningfully 4→8, diminishing returns beyond
DEFAULT_LORA_STEPS = 28  # dev-trained LoRAs benefit from more steps


def _get_url() -> str:
    load_dotenv_once()
    return os.environ.get("LOCAL_FLUX_URL", DEFAULT_URL)


def generate(
    prompt: str,
    reference_image_bytes: bytes | None = None,
    strength: float = 0.65,
    num_steps: int = DEFAULT_STEPS,
) -> bytes:
    """Generate an image via the local FLUX server. Returns PNG bytes.

    When *reference_image_bytes* is provided, uses the img2img endpoint.
    *strength* controls how much the reference conditions the output
    (0 = copy reference, 1 = ignore it entirely).
    *num_steps* is passed directly to num_inference_steps on the server.
    """
    url = _get_url()

    try:
        if reference_image_bytes:
            resp = httpx.post(
                f"{url}/img2img",
                data={
                    "prompt": prompt,
                    "width": 1024,
                    "height": 768,
                    "num_inference_steps": num_steps,
                    "strength": strength,
                },
                files={"image": ("reference.jpg", reference_image_bytes, "image/jpeg")},
                timeout=TIMEOUT,
            )
        else:
            resp = httpx.post(
                f"{url}/generate",
                json={
                    "prompt": prompt,
                    "width": 1024,
                    "height": 768,
                    "num_inference_steps": num_steps,
                },
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


def generate_with_lora(
    prompt: str,
    lora_scale: float = 0.65,
    num_steps: int = DEFAULT_LORA_STEPS,
    guidance_scale: float = 3.5, # Lower is better for the "painterly" look
) -> bytes:
    """Generate via the local FLUX server using a LoRA adapter. Returns PNG bytes."""
    url = _get_url()

    try:
        resp = httpx.post(
            f"{url}/generate-lora",
            json={
                "prompt": prompt,
                "lora_repo": "strangerzonehf/Ghibli-Flux-Cartoon-LoRA",
                "lora_scale": lora_scale,
                "guidance_scale": guidance_scale,
                "width": 1024,
                "height": 768,
                "num_inference_steps": num_steps,
                "seed": -1 # Randomize by default for variety
            },
            timeout=TIMEOUT,
        )
    except httpx.ConnectError as e:
        raise ImageGenerationError(
            f"Local FLUX server not reachable at {url}. "
            "Is flux_server.py running?"
        ) from e
    except httpx.TimeoutException as e:
        raise ImageGenerationError("Local FLUX LoRA generation timed out") from e

    if resp.status_code != 200:
        raise ImageGenerationError(
            f"Local FLUX LoRA error ({resp.status_code}): {resp.text[:200]}"
        )

    return resp.content
