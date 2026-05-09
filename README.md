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
