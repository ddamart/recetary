"""Shared models, prompt, and helpers for recipe extraction backends."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..models import (
    Difficulty,
    IngredientCategory,
    IngredientRef,
    RecipeCreate,
    SourceType,
    StepIn,
)


def load_dotenv_once() -> None:
    """Lightweight .env loader so SDKs pick up API keys without
    requiring callers to source the file explicitly."""
    repo_root = Path(__file__).resolve().parents[3]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class ExtractionError(RuntimeError):
    """Raised when the LLM returns no structured output."""


class IngredientDraft(BaseModel):
    """A single ingredient as extracted by the LLM."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(description="Canonical lowercase Spanish name, e.g. 'cebolla'")
    category: IngredientCategory = Field(
        description="One of: protein, vegetable, legume, fruit, grain, dairy, fat, "
        "seasoning, sauce, beverage, nut, other"
    )
    quantity_raw: Optional[str] = Field(
        default=None,
        description="Original quantity verbatim, e.g. '400 gramos', '1 sobre', '1 cucharadita'",
    )
    is_pantry: bool = Field(
        default=False,
        description="True for pantry staples (oil, salt, pepper, flour, common spices, "
        "garlic). HelloFresh marks these as 'De tu despensa'.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional preparation note, e.g. 'picada fina', 'para adobar'",
    )


class StepDraft(BaseModel):
    """A single preparation step."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(
        default=None,
        description="Optional short heading, e.g. 'Hornea las patatas'",
    )
    text: str = Field(description="Body of the step, in Spanish")


class RecipeDraft(BaseModel):
    """The AI-extracted recipe payload, before the caller attaches source info."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(description="Full recipe title in Spanish")
    subtitle: Optional[str] = Field(
        default=None,
        description="Short secondary line complementing the title; always generate one",
    )
    source_ref: Optional[str] = Field(
        default=None,
        description="Original source URL or filename, set by the extract endpoint",
    )
    description: Optional[str] = Field(
        default=None, description="One- or two-sentence summary in Spanish"
    )
    servings: int = Field(default=2)
    total_time_min: Optional[int] = Field(
        default=None, description="Total time including prep, in minutes"
    )
    cook_time_min: Optional[int] = Field(
        default=None, description="Active cooking time, in minutes"
    )
    difficulty: Optional[Difficulty] = Field(default=None)
    ingredients: list[IngredientDraft] = Field(default_factory=list)
    steps: list[StepDraft] = Field(default_factory=list)
    utensils: list[str] = Field(
        default_factory=list,
        description="Tools needed, in Spanish (e.g. 'sartén con tapa', 'bandeja de horno')",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Short Spanish labels: cuisine, audience, method, etc.",
    )


SYSTEM_INSTRUCTIONS = """You are a culinary data extractor for a personal recipe collection.

Your task is to read a recipe — supplied as a PDF document, an image, plain text, or web-article text — and return a fully populated Recipe object that conforms to the provided JSON schema.

# Language

- Every recipe field MUST be in Spanish, exactly as a Spanish-speaking home cook would write it.
- Ingredient names use the canonical lowercase Spanish form: "patata" (not "Patatas"), "queso mozzarella" (not "Mozzarella"), "carne picada" (not "Carne de ternera y cerdo picada"; collapse compound HelloFresh names to a generic short form when reasonable).
- Step text, titles, utensils, and tags stay in Spanish. Do NOT translate to English.

# Ingredients

For each ingredient produce one IngredientDraft object:

- `name`: canonical, lowercase, singular when possible, no quantities. Examples:
  - "Patata" → "patata"
  - "Queso Mozzarella" → "queso mozzarella"
  - "Brotes de espinacas" → "espinacas"
  - "Carne de ternera y cerdo picada" → "carne picada"
  - "Tomate triturado" → "tomate triturado" (keep, the form matters)
- `category`: one of protein, vegetable, legume, fruit, grain, dairy, fat, seasoning, sauce, beverage, nut, other. Choose the closest fit:
  - protein: meat, fish, eggs, tofu
  - vegetable: fresh vegetables, mushrooms, fresh herbs (cilantro, parsley)
  - legume: beans, lentils, chickpeas, peas
  - fruit: fresh fruits including tomatoes when treated as fruit; avocado
  - grain: rice, pasta, bread, flour, oats, quinoa, bulgur, gnocchi
  - dairy: milk, cheese, yogurt, butter, cream
  - fat: oils (olive, sunflower), bacon (when used as fat), lard
  - seasoning: dried spices, dried herbs, garlic, salt, pepper, sugar
  - sauce: ready-made sauces, mustard, soy sauce, tomato sauce in tube
  - beverage: liquids meant to drink (rare in recipes; otherwise use "other")
  - nut: almonds, walnuts, sesame seeds, peanuts
  - other: anything that does not fit above
- `quantity_raw`: copy the source string verbatim. Do not normalize units. Examples: "400 gramos", "1 sobre", "1 cucharadita", "2 dientes", "al gusto". Use null only if the recipe gives no quantity at all.
- `is_pantry`: true for staples that the HelloFresh PDFs label "De tu despensa" (typically: aceite de oliva, sal, pimienta, harina, ajo, orégano y otras especias secas, vinagre, azúcar). Set false for everything else.
- `notes`: short preparation note like "picada fina", "para adobar", "cortado en gajos". Optional.

If an existing canonical ingredient list is provided in the user message, prefer those exact names so the database can deduplicate.

# Steps

- Preserve order. Each step is one StepDraft.
- `title`: a short heading summarizing the main action of the step (e.g. "Hornea las patatas", "Prepara las verduras", "Monta la lasaña"). Use the source's heading if one exists; otherwise generate a concise one yourself. Always provide a title.
- `text`: full body of the step in Spanish, complete sentences. Do not abbreviate or summarize aggressively, but you may drop redundant exhortations like "¡Que aproveche!" if they are not part of the instructions.

# Other fields

- `title`: the full elaborate Spanish title, using sentence case (only the first word capitalized, e.g. "Fideos con aceite de chile y cacahuete", not "Fideos con Aceite de Chile y Cacahuete"). Proper nouns stay capitalized. Include the leading "¡Polpette!" or similar prefix when present. Avoid splash labels like "Familia" — those go in `tags`.
- `subtitle`: a short secondary line that complements the title (e.g. "con patatas al horno y salsa de yogur"). Always provide a subtitle. If the source has a separate subtitle, use it. Otherwise, split the full title: keep the dish name as `title` and move the accompaniments, sauce, or technique to `subtitle`. If the title is already short and cannot be split, write a brief phrase describing the main side, sauce, or cooking style (e.g. "al horno con verduras"). Never leave this null.
- `description`: a short one- or two-sentence Spanish blurb. Use the source's intro text when available; otherwise summarize.
- `servings`: integer. HelloFresh PDFs default to 2 unless they show a 4-person column; use the smaller value.
- `total_time_min`: total time including prep, in minutes. The HelloFresh "Listo en" value.
- `cook_time_min`: active cooking time, in minutes. The HelloFresh "Cocinando" value.
- `difficulty`: easy, medium, or hard. Infer when not stated: easy ≤ 30 min one-pot, medium ≤ 45 min, hard otherwise.
- `utensils`: list the tools the source mentions ("sartén con tapa", "bandeja de horno con papel", "colador", "bol grande"). Lowercase phrase, no leading article.
- `tags`: short Spanish labels for filtering. Include cuisine ("italiana", "asiática", "mexicana", "mediterránea"), audience ("familia", "vegetariano", "vegano"), and method when distinctive ("horno", "wok", "parrilla"). Keep to 1–4 tags. Use lowercase.

# Output

Return only the structured object via the provided output schema. Do not add commentary outside the structured response.
"""


def build_canonical_preamble(canonical_ingredients: Iterable[str]) -> str:
    """Build the preamble text listing existing canonical ingredients."""
    canonical = sorted(set(canonical_ingredients))
    if canonical:
        return (
            "Existing canonical ingredient names (prefer these exact spellings "
            "when an ingredient matches):\n"
            + "\n".join(f"- {name}" for name in canonical)
        )
    return (
        "There are no existing canonical ingredients yet — propose new ones "
        "with their categories."
    )


def draft_to_create(
    draft: RecipeDraft,
    *,
    source_type: SourceType,
    source_ref: Optional[str] = None,
    raw_text: Optional[str] = None,
    image_path: Optional[str] = None,
) -> RecipeCreate:
    """Combine an extracted draft with caller-supplied source metadata."""
    return RecipeCreate(
        title=draft.title,
        subtitle=draft.subtitle,
        description=draft.description,
        servings=max(1, min(20, draft.servings)),
        total_time_min=draft.total_time_min,
        cook_time_min=draft.cook_time_min,
        difficulty=draft.difficulty,
        image_path=image_path,
        source_type=source_type,
        source_ref=source_ref,
        raw_text=raw_text,
        ingredients=[
            IngredientRef(
                name=i.name,
                category=i.category,
                quantity_raw=i.quantity_raw,
                notes=i.notes,
                is_pantry=i.is_pantry,
            )
            for i in draft.ingredients
        ],
        steps=[StepIn(title=s.title, text=s.text) for s in draft.steps],
        utensils=list(draft.utensils),
        tags=list(draft.tags),
    )
