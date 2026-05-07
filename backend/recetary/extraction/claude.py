"""Claude-powered structured recipe extraction.

The extractor accepts any combination of PDF / image / text content and
returns a `RecipeDraft` validated against a Pydantic schema via
`client.messages.parse()`. The caller converts the draft into a
`RecipeCreate` by attaching source metadata.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Iterable, Literal, Optional

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from ..models import (
    Difficulty,
    IngredientCategory,
    IngredientRef,
    RecipeCreate,
    SourceType,
    StepIn,
)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096


def _load_dotenv_once() -> None:
    """Lightweight .env loader so the SDK picks up ANTHROPIC_API_KEY without
    requiring callers to source the file explicitly."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
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
    """Raised when Claude returns no structured output."""


class IngredientDraft(BaseModel):
    """A single ingredient as extracted by Claude."""

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
    subtitle: Optional[str] = Field(default=None)
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
- `title`: the short bold heading from the source (e.g. "Hornea las patatas"). Optional if the source has no headings.
- `text`: full body of the step in Spanish, complete sentences. Do not abbreviate or summarize aggressively, but you may drop redundant exhortations like "¡Que aproveche!" if they are not part of the instructions.

# Other fields

- `title`: the full elaborate Spanish title, including the leading "¡Polpette!" or similar prefix when present. Avoid splash labels like "Familia" — those go in `tags`.
- `subtitle`: the secondary line under the title (e.g. "con patatas al horno"). Null if absent.
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


_extractor_singleton: Optional["RecipeExtractor"] = None


def get_extractor(model: str = DEFAULT_MODEL) -> "RecipeExtractor":
    global _extractor_singleton
    if _extractor_singleton is None or _extractor_singleton.model != model:
        _extractor_singleton = RecipeExtractor(model=model)
    return _extractor_singleton


class RecipeExtractor:
    def __init__(self, *, model: str = DEFAULT_MODEL) -> None:
        _load_dotenv_once()
        self.client = anthropic.Anthropic()
        self.model = model

    def _system(self) -> list[dict]:
        return [
            {
                "type": "text",
                "text": SYSTEM_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _build_user_content(
        self,
        *,
        canonical_ingredients: Iterable[str],
        text: Optional[str],
        pdf_bytes: Optional[bytes],
        image_bytes: Optional[bytes],
        image_media_type: Optional[str],
        source_hint: Optional[str],
    ) -> list[dict]:
        canonical = sorted(set(canonical_ingredients))
        if canonical:
            preamble = (
                "Existing canonical ingredient names (prefer these exact spellings "
                "when an ingredient matches):\n"
                + "\n".join(f"- {name}" for name in canonical)
            )
        else:
            preamble = (
                "There are no existing canonical ingredients yet — propose new ones "
                "with their categories."
            )

        content: list[dict] = [{"type": "text", "text": preamble}]

        if pdf_bytes is not None:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                    },
                }
            )
        if image_bytes is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type or "image/jpeg",
                        "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                    },
                }
            )
        if text:
            content.append(
                {"type": "text", "text": f"Recipe text:\n\n{text.strip()}"}
            )

        prompt = "Extract the recipe from the source above into the structured schema."
        if source_hint:
            prompt += f"\n\nSource hint: {source_hint}"
        content.append({"type": "text", "text": prompt})
        return content

    def _tool_definition(self) -> dict:
        """Build the single tool that forces the model to emit a RecipeDraft."""
        schema = RecipeDraft.model_json_schema()
        return {
            "name": "submit_recipe",
            "description": "Submit the structured recipe extracted from the source.",
            "input_schema": schema,
        }

    def extract(
        self,
        *,
        canonical_ingredients: Iterable[str] = (),
        text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        image_bytes: Optional[bytes] = None,
        image_media_type: Optional[str] = None,
        source_hint: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> RecipeDraft:
        if not any((text, pdf_bytes, image_bytes)):
            raise ValueError("extract() requires at least one of text, pdf_bytes, image_bytes")

        user_content = self._build_user_content(
            canonical_ingredients=canonical_ingredients,
            text=text,
            pdf_bytes=pdf_bytes,
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            source_hint=source_hint,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(),
            tools=[self._tool_definition()],
            tool_choice={"type": "tool", "name": "submit_recipe"},
            messages=[{"role": "user", "content": user_content}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_recipe":
                return RecipeDraft.model_validate(block.input)

        raise ExtractionError(
            f"Claude returned no submit_recipe tool call (stop_reason={response.stop_reason!r})"
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
