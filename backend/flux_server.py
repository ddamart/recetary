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
from contextlib import asynccontextmanager

import torch
from diffusers import BitsAndBytesConfig, FluxPipeline, FluxTransformer2DModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("flux_server")
logging.basicConfig(level=logging.INFO)

MODEL_ID = "black-forest-labs/FLUX.1-schnell"

pipe: FluxPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
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

    logger.info("FLUX Schnell ready.")
    yield
    pipe = None


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

    logger.info("Generating image: %s", req.prompt[:200])
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
