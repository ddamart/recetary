# Recetary

Personal recipe book with ingredient-based search, fuzzy title lookup, random
recipe picker, and AI-powered import from PDF, image, plain text, and web URLs.

## Stack

- **Backend:** Python 3.10+ / FastAPI / SQLite (FTS5) / rapidfuzz
- **Frontend:** Next.js 16 / React 19 / Tailwind v4
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) for structured extraction

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
GET  /search                 ?q=&ingredients=&tag=&limit=&offset=
GET  /ingredients            ?q=
GET  /static/images/{name}   Recipe cover images
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

## Notes

- All code, docs, identifiers, and enums are in English.
- User-facing recipe content (titles, ingredient names, steps, tags) is Spanish.
- `data/recetary.db` is gitignored. So are `raw_pdfs/` and `raw_imgs/` — the
  seed corpus stays local. Switch to git-lfs if you want to version it.
- `.env` holds `ANTHROPIC_API_KEY` and is gitignored. `.env.example` is the
  template.
