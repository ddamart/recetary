"""Pydantic models for recipes, ingredients, steps."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

IngredientCategory = Literal[
    "protein", "vegetable", "legume", "fruit", "grain",
    "dairy", "fat", "seasoning", "sauce", "beverage",
    "nut", "other",
]

Difficulty = Literal["easy", "medium", "hard"]
SourceType = Literal["pdf", "image", "text", "url", "manual"]


class IngredientRef(BaseModel):
    """An ingredient as referenced inside a recipe (input form)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    category: IngredientCategory = "other"
    quantity_raw: Optional[str] = None
    quantity_value: Optional[float] = None
    quantity_unit: Optional[str] = None
    notes: Optional[str] = None
    is_pantry: bool = False


class IngredientOut(BaseModel):
    id: int
    name: str
    category: IngredientCategory


class RecipeIngredientOut(BaseModel):
    ingredient: IngredientOut
    quantity_raw: Optional[str]
    quantity_value: Optional[float]
    quantity_unit: Optional[str]
    notes: Optional[str]
    is_pantry: bool


class StepIn(BaseModel):
    title: Optional[str] = None
    text: str = Field(min_length=1)
    image_path: Optional[str] = None


class StepOut(StepIn):
    step_number: int


class RecipeCreate(BaseModel):
    """Payload accepted from the add/extract flow."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    subtitle: Optional[str] = None
    description: Optional[str] = None
    servings: Optional[int] = Field(default=2, ge=1, le=20)
    total_time_min: Optional[int] = Field(default=None, ge=0)
    cook_time_min: Optional[int] = Field(default=None, ge=0)
    difficulty: Optional[Difficulty] = None
    image_path: Optional[str] = None
    source_type: SourceType = "manual"
    source_ref: Optional[str] = None
    raw_text: Optional[str] = None

    ingredients: list[IngredientRef] = Field(default_factory=list)
    steps: list[StepIn] = Field(default_factory=list)
    utensils: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class RecipeSummary(BaseModel):
    id: int
    title: str
    subtitle: Optional[str]
    image_path: Optional[str]
    total_time_min: Optional[int]
    servings: Optional[int]
    ingredient_count: int
    tags: list[str]


class RecipeMatch(RecipeSummary):
    """Search result enriched with ingredients the user did not list."""

    missing_ingredients: list[str] = Field(default_factory=list)
    matched_ingredients: list[str] = Field(default_factory=list)


class Recipe(BaseModel):
    id: int
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    servings: Optional[int]
    total_time_min: Optional[int]
    cook_time_min: Optional[int]
    difficulty: Optional[Difficulty]
    image_path: Optional[str]
    source_type: SourceType
    source_ref: Optional[str]
    created_at: str
    ingredients: list[RecipeIngredientOut]
    steps: list[StepOut]
    utensils: list[str]
    tags: list[str]
