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

MODEL_ID = "black-forest-labs/FLUX.1-schnell"

pipe: FluxPipeline | None = None
img2img_pipe: FluxImg2ImgPipeline | None = None
_generate_lock = threading.Lock()


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


class GenerateRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 768
    num_inference_steps: int = 4


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
            guidance_scale=0.0,
        ).images[0]

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    finally:
        _generate_lock.release()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
