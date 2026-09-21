# Recetary

Personal recipe book with ingredient-based search, fuzzy title lookup, random
recipe picker, and AI-powered import from PDF, image, plain text, and web URLs.

## Stack

- **Backend:** Python 3.10+ / FastAPI / SQLite (FTS5) / rapidfuzz
- **Frontend:** Next.js 16 / React 19 / Tailwind v4
- **AI:** Pluggable LLM and image generation backends (see below)

## One-shot dev startup

After the first-time setup below, every subsequent session is just:

```powershell
.\scripts\dev.ps1
```

Opens FastAPI (http://localhost:8000) and Next.js (http://localhost:3000) in
two terminal windows so their logs stay visible. Close the windows or Ctrl+C
to stop.

## First-time setup

```powershell
# 1. Python venv + backend (editable install)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"

# 2. Database
.\.venv\Scripts\recetary.exe init

# 3. Optional: bulk-import the HelloFresh seed corpus (~2 € of API)
copy .env.example .env   # then paste your ANTHROPIC_API_KEY into .env
.\.venv\Scripts\recetary.exe import-pdfs raw_pdfs

# 4. Frontend dependencies
cd frontend ; npm install ; cd ..
```

## CLI

```
recetary init                        Create database and load schema
recetary import-pdfs raw_pdfs/       Bulk-extract every PDF in a folder
recetary add --pdf path.pdf          AI-extract a single PDF
recetary add --image path.png        AI-extract from an image
recetary add --text PATH_OR_DASH     AI-extract from plain text (- = stdin)
recetary add --url https://...       AI-extract from a web article
recetary add-json path.json          Insert from a structured JSON file (no AI)
recetary list                        Show stored recipes
```

## API

Started by `dev.ps1` at http://localhost:8000 — interactive docs at `/docs`.

```
GET  /recipes                ?limit=&offset=&tag=
POST /recipes                Commit a (reviewed) RecipeCreate
GET  /recipes/{id}
PUT  /recipes/{id}
DELETE /recipes/{id}
GET  /recipes/random         ?ingredients=&tag=
POST /recipes/extract        Multipart: source_type + file/text/url → RecipeDraft
POST /recipes/generate-image Generate a styled cover image for a recipe
GET  /info                   Returns active extractor and image backends
GET  /search                 ?q=&ingredients=&tag=&limit=&offset=
GET  /search/count           ?q=&ingredients=&tag=
GET  /ingredients            ?q=
GET  /image-styles           Available image style presets
GET  /static/images/{name}   Recipe cover images
```

## AI backends

Controlled via environment variables in `.env` (see `.env.example`).

### Recipe extraction (`EXTRACTOR_BACKEND`)

Parses recipes from PDF, image, plain text, URL, and video sources.

| Value    | Provider        | Required env var      | Notes                          |
|----------|-----------------|-----------------------|--------------------------------|
| `claude` | Anthropic Claude (default) | `ANTHROPIC_API_KEY` | All source types               |
| `gemini` | Google Gemini   | `GOOGLE_API_KEY`      | All source types; required for Twitter/X video |

### Image generation (`IMAGE_BACKEND`)

Generates styled cover images for recipes. The prompt pipeline (Gemini Flash
translation + style frame) is shared — only the final image generation differs.

| Value     | Provider            | Required env var      | Cost              |
|-----------|---------------------|-----------------------|-------------------|
| `imagen`  | Google Imagen (default) | `GOOGLE_API_KEY`  | ~70/day free, then $0.03/img |
| `together`| Together AI (FLUX Schnell) | `TOGETHER_API_KEY` | $0.003/img       |
| `local`   | Local FLUX Schnell  | (none)                | Free (your GPU)   |

**Note:** `imagen` and `together` are cloud APIs — no extra server needed.
`local` requires running `flux_server.py` as a separate process (see below).

### Local FLUX server (optional)

Only needed when `IMAGE_BACKEND=local`. Runs FLUX Schnell on your GPU.
Requires an NVIDIA GPU with ≥16 GB VRAM (tested on RTX 4080 SUPER).

**One-time setup:**

```powershell
# 1. Install ML deps with CUDA support (CPU-only torch will NOT work)
.\.venv\Scripts\pip.exe install -r backend/requirements-flux.txt --extra-index-url https://download.pytorch.org/whl/cu126

# 2. Accept the FLUX Schnell license (instant approval)
#    Visit https://huggingface.co/black-forest-labs/FLUX.1-schnell
#    and click "Agree and access repository"

# 3. Log in so the model can be downloaded (~12 GB, cached after first run)
.\.venv\Scripts\huggingface-cli.exe login
```

**Running:** The dev scripts (`dev.ps1` / `dev.sh`) auto-start the FLUX server
when `IMAGE_BACKEND=local` is set in `.env`. To run it manually:

```powershell
.\.venv\Scripts\python.exe backend/flux_server.py
```

Defaults to `http://localhost:8500`. Override with `LOCAL_FLUX_URL` env var.
Set `LOCAL_FLUX_MODEL` before starting the server to test another compatible
Diffusers model; changing it requires a server restart. The production default
remains Imagen.

### Image benchmark

The benchmark uses three fixed food prompts and deterministic seeds. It writes
one PNG per backend/recipe and `report.json` with the selected model, seed,
steps, latency, output size, and error text. It does not download weights or
change the production backend:

```powershell
# Local only (server must already be running)
.\.venv\Scripts\recetary.exe benchmark-images --backend local --output data/image-benchmark

# Compare configured backends; cloud backends require their API keys
.\.venv\Scripts\recetary.exe benchmark-images `
  --backend imagen --backend together --backend local `
  --seed 20260921 --steps 8
```

Compare candidates only at the same resolution, prompt set, seed, and step
count. Prefer a candidate only when it improves visual fidelity and food
identity without unacceptable latency, VRAM, errors, or license restrictions.
The benchmark records latency and errors; local `/info` exposes model/device
and current CUDA allocation when queried, but VRAM is not available for cloud
backends. Imagen does not expose a reproducible seed in this path, so its
seed is recorded as a comparison label, not a determinism guarantee.

Candidate facts (verify before deployment):

| Candidate | Practical configuration | License/hardware notes |
|---|---|---|
| FLUX.2 Klein 4B | Apache 2.0; official guidance ranges from ~8 GB (repo) to ~13 GB (model card) | 9B is under BFL's non-commercial license; no official numeric 9B VRAM figure |
| Qwen Image | 20B, Apache 2.0 | Official sources reviewed do not publish numeric VRAM requirements |
| Z-Image-Turbo | 6B, Apache 2.0; official README says it fits within 16 GB VRAM | Other Z-Image variants need separate license/hardware verification |
| SD3.5 / SDXL | SD3.5 Medium is 2.5B and officially states 9.9 GB excluding text encoders; SD3.5 uses Stability Community License | SDXL Base/Refiner use OpenRAIL++; official cards do not state numeric VRAM |

Official references: [FLUX.2 Klein](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B),
[Qwen Image](https://huggingface.co/Qwen/Qwen-Image),
[Z-Image](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo),
[Stable Diffusion 3.5](https://stability.ai/news/introducing Stable Diffusion 3.5),
and [SDXL](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

## Notes

- All code, docs, identifiers, and enums are in English.
- User-facing recipe content (titles, ingredient names, steps, tags) is Spanish.
- `data/recetary.db` is gitignored. So are `raw_pdfs/` and `raw_imgs/` — the
  seed corpus stays local. Switch to git-lfs if you want to version it.
- `.env` holds API keys and backend selection and is gitignored. `.env.example`
  is the template — see also `backend/.env.example` for the full list.
