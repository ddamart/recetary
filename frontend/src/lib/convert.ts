import type { Recipe, RecipeDraft } from "./types";

/** Convert a full Recipe (API response) to a RecipeDraft (form shape). */
export function recipeToDraft(recipe: Recipe): RecipeDraft {
  return {
    title: recipe.title,
    subtitle: recipe.subtitle,
    description: recipe.description,
    servings: recipe.servings,
    total_time_min: recipe.total_time_min,
    cook_time_min: recipe.cook_time_min,
    difficulty: recipe.difficulty,
    ingredients: recipe.ingredients.map((ri) => ({
      name: ri.ingredient.name,
      category: ri.ingredient.category,
      quantity_raw: ri.quantity_raw,
      is_pantry: ri.is_pantry,
      notes: ri.notes,
    })),
    steps: recipe.steps.map((s) => ({ title: s.title, text: s.text })),
    utensils: recipe.utensils,
    tags: recipe.tags,
  };
}
