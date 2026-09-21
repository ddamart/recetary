"""Standalone FLUX Schnell image generation server.

Run with:
    uvicorn flux_server:app --port 8500

The model loads on startup (~30s first time, ~10s after caching). Once ready,
each image takes ~5-15s on an RTX 4080 SUPER.

Requirements: install from requirements-flux.txt
    pip install -r requirements-flux.txt
"""
from __future__ import annotations

import io
import logging
import os
import threading
from contextlib import asynccontextmanager

import torch
from diffusers import (
    BitsAndBytesConfig,
    FluxImg2ImgPipeline,
    FluxPipeline,
    FluxTransformer2DModel,
)
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger("flux_server")
logging.basicConfig(level=logging.INFO)

DEFAULT_MODEL_ID = "black-forest-labs/FLUX.1-schnell"
MODEL_ID = os.environ.get("LOCAL_FLUX_MODEL", DEFAULT_MODEL_ID)

pipe: FluxPipeline | None = None
img2img_pipe: FluxImg2ImgPipeline | None = None
_generate_lock = threading.Lock()

# Tracks which LoRA repo is currently loaded (None = no LoRA loaded).
# LoRA is loaded lazily on the first /generate-lora request for a given repo
# and kept resident so subsequent calls skip the load step.
_loaded_lora_repo: str | None = None
_LORA_ADAPTER_NAME = "lora_0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe, img2img_pipe
    logger.info("Loading FLUX Schnell (NF4 quantised)...")

    # Load the transformer (largest component) in NF4 to fit in 16 GB VRAM
    nf4_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    transformer = FluxTransformer2DModel.from_pretrained(
        MODEL_ID,
        subfolder="transformer",
        quantization_config=nf4_config,
        torch_dtype=torch.bfloat16,
    )
    pipe = FluxPipeline.from_pretrained(
        MODEL_ID,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_model_cpu_offload()

    # Build img2img pipeline sharing all components (no extra VRAM)
    img2img_pipe = FluxImg2ImgPipeline(
        transformer=pipe.transformer,
        scheduler=pipe.scheduler,
        vae=pipe.vae,
        text_encoder=pipe.text_encoder,
        text_encoder_2=pipe.text_encoder_2,
        tokenizer=pipe.tokenizer,
        tokenizer_2=pipe.tokenizer_2,
    )
    img2img_pipe.enable_model_cpu_offload()

    logger.info("FLUX Schnell ready (txt2img + img2img).")
    yield
    pipe = None
    img2img_pipe = None


app = FastAPI(title="FLUX Schnell Server", lifespan=lifespan)


def _ensure_lora_loaded(lora_repo: str) -> None:
    """Load *lora_repo* as the active LoRA adapter (noop if already loaded)."""
    global _loaded_lora_repo
    if _loaded_lora_repo == lora_repo:
        return
    if _loaded_lora_repo is not None:
        logger.info("Unloading previous LoRA: %s", _loaded_lora_repo)
        pipe.unload_lora_weights()
    logger.info("Loading LoRA weights: %s", lora_repo)
    pipe.load_lora_weights(lora_repo, adapter_name=_LORA_ADAPTER_NAME)
    _loaded_lora_repo = lora_repo
    logger.info("LoRA ready: %s", lora_repo)


class GenerateRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 768
    num_inference_steps: int = 4
    seed: int | None = None


@app.get("/info")
def info() -> dict[str, object]:
    memory: dict[str, int] = {}
    if torch.cuda.is_available():
        memory = {
            "vram_allocated_bytes": torch.cuda.memory_allocated(),
            "vram_reserved_bytes": torch.cuda.memory_reserved(),
        }
    return {"model": MODEL_ID, "device": "cuda" if torch.cuda.is_available() else "cpu", **memory}


@app.post("/generate")
def generate(req: GenerateRequest):
    if pipe is None:
        raise HTTPException(503, "Model not loaded yet")

    # Serialize requests — the pipeline is not thread-safe and the GPU
    # can only run one generation at a time anyway.
    if not _generate_lock.acquire(blocking=False):
        raise HTTPException(429, "Generation already in progress, try again shortly")

    try:
        logger.info("Generating image (txt2img): %s", req.prompt[:200])
        image = pipe(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=0.0,
            generator=torch.Generator(device="cuda").manual_seed(req.seed)
            if req.seed is not None
            else None,
        ).images[0]

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    finally:
        _generate_lock.release()


@app.post("/img2img")
def img2img(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    width: int = Form(1024),
    height: int = Form(768),
    num_inference_steps: int = Form(4),
    strength: float = Form(0.65),
):
    if img2img_pipe is None:
        raise HTTPException(503, "Model not loaded yet")

    if not _generate_lock.acquire(blocking=False):
        raise HTTPException(429, "Generation already in progress, try again shortly")

    try:
        # Decode and resize reference image to target dimensions
        ref_image = Image.open(io.BytesIO(image.file.read())).convert("RGB")
        ref_image = ref_image.resize((width, height), Image.LANCZOS)

        logger.info("Generating image (img2img, strength=%.2f): %s", strength, prompt[:200])
        result = img2img_pipe(
            prompt=prompt,
            image=ref_image,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            strength=strength,
            guidance_scale=3.5,
        ).images[0]

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    finally:
        _generate_lock.release()


class GenerateLoraRequest(BaseModel):
    prompt: str
    lora_repo: str
    lora_scale: float = 0.85
    width: int = 1024
    height: int = 768
    # Dev-trained LoRAs need more steps than schnell's default 4 to express the style.
    num_inference_steps: int = 20


@app.post("/generate-lora")
def generate_lora(req: GenerateLoraRequest):
    if pipe is None:
        raise HTTPException(503, "Model not loaded yet")

    if not _generate_lock.acquire(blocking=False):
        raise HTTPException(429, "Generation already in progress, try again shortly")

    try:
        _ensure_lora_loaded(req.lora_repo)
        pipe.set_adapters([_LORA_ADAPTER_NAME], adapter_weights=[req.lora_scale])

        logger.info(
            "Generating image (lora=%s, scale=%.2f): %s",
            req.lora_repo, req.lora_scale, req.prompt[:200],
        )
        image = pipe(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=3.5,
        ).images[0]

        # Reset adapter weight so regular /generate calls are unaffected.
        pipe.set_adapters([_LORA_ADAPTER_NAME], adapter_weights=[0.0])

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception:
        try:
            pipe.set_adapters([_LORA_ADAPTER_NAME], adapter_weights=[0.0])
        except Exception:
            pass
        raise
    finally:
        _generate_lock.release()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
