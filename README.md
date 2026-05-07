# Recetary

Personal recipe book with ingredient-based search, fuzzy title lookup, random
recipe picker, and AI-powered import from PDF, image, plain text, and web URLs.

## Stack

- **Backend:** Python 3.10+ / FastAPI / SQLite (FTS5 + spellfix1)
- **Frontend:** Next.js 15 / React 19 / Tailwind / shadcn/ui
- **AI:** Anthropic Claude (sonnet-4-6) for structured extraction

## Quick start

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e backend
python -m recetary init
uvicorn recetary.main:app --reload --app-dir backend

# Frontend (separate shell)
cd frontend
npm install
npm run dev
```

## CLI

```
recetary init                        Create database and load schema
recetary import-pdfs raw_pdfs/       Bulk-extract every PDF in a folder
recetary add --pdf path.pdf
recetary add --image path.png
recetary add --text - < recipe.txt
recetary add --url https://...
recetary search --ingredient onion --ingredient tomato
recetary random
recetary export --json out.json
```

## Notes

- All code, docs, identifiers, and enums are in English.
- User-facing recipe content (titles, ingredient names, steps, tags) is Spanish.
- `data/recetary.db` is gitignored; the `raw_pdfs/` and `raw_imgs/` folders
  contain the seed corpus (HelloFresh recipes).
