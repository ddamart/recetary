"""Reproducible image-backend benchmark.

This intentionally exercises configured backends only; it never downloads or
changes model weights. Results are PNG files plus a JSON report.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

RECIPES = (
    ("tomato-pasta", "A bowl of tomato basil pasta with parmesan on a rustic ceramic plate."),
    ("vegetable-curry", "A colorful vegetable curry with rice, herbs, and toasted cashews."),
    ("apple-tart", "A golden apple tart with cinnamon, powdered sugar, and crisp pastry."),
)


def _model_name(backend: str) -> str:
    defaults = {
        "imagen": "imagen-4.0-fast-generate-001",
        "together": "black-forest-labs/FLUX.1-schnell",
        "local": "black-forest-labs/FLUX.1-schnell",
    }
    return os.environ.get(
        {"local": "LOCAL_FLUX_MODEL", "together": "TOGETHER_MODEL"}.get(backend, ""),
        defaults[backend],
    )


def _local_runtime() -> dict[str, object]:
    url = os.environ.get("LOCAL_FLUX_URL", "http://localhost:8500")
    try:
        response = httpx.get(f"{url}/info", timeout=3)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return {}


def run(output: Path, backends: list[str], seed: int, steps: int) -> int:
    from .extraction.imagen import generate_benchmark_image

    output.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, object]] = []
    for backend in backends:
        os.environ["IMAGE_BACKEND"] = backend
        for offset, (recipe_id, prompt) in enumerate(RECIPES):
            current_seed = seed + offset
            item: dict[str, object] = {
                "backend": backend,
                "model": _model_name(backend),
                "recipe": recipe_id,
                "seed": current_seed,
                "steps": steps,
                "prompt": prompt,
            }
            if backend == "local":
                item["runtime"] = _local_runtime()
            started = time.perf_counter()
            try:
                png = generate_benchmark_image(prompt, current_seed, steps)
                path = output / f"{backend}-{recipe_id}-seed{current_seed}.png"
                path.write_bytes(png)
                item.update({"status": "ok", "output": str(path), "bytes": len(png)})
            except Exception as exc:
                item.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            item["latency_seconds"] = round(time.perf_counter() - started, 3)
            report.append(item)
            print(json.dumps(item, ensure_ascii=False))

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0 if all(item["status"] == "ok" for item in report) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", action="append", dest="backends",
                        choices=("imagen", "together", "local"),
                        help="Backend to test; repeatable (default: IMAGE_BACKEND)")
    parser.add_argument("--output", type=Path, default=Path("data/image-benchmark"))
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--steps", type=int, default=8)
    args = parser.parse_args(argv)
    backends = args.backends or [os.environ.get("IMAGE_BACKEND", "imagen").lower()]
    return run(args.output, backends, args.seed, args.steps)


if __name__ == "__main__":
    raise SystemExit(main())
