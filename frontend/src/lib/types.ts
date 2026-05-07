// Mirrors the Pydantic models in backend/recetary/models.py

export type IngredientCategory =
  | "protein" | "vegetable" | "legume" | "fruit" | "grain"
  | "dairy" | "fat" | "seasoning" | "sauce" | "beverage" | "nut" | "other";

export const CATEGORY_LABEL_ES: Record<IngredientCategory, string> = {
  protein: "Proteína",
  vegetable: "Vegetal",
  legume: "Legumbre",
  fruit: "Fruta",
  grain: "Cereal",
  dairy: "Lácteo",
  fat: "Grasa",
  seasoning: "Condimento",
  sauce: "Salsa",
  beverage: "Bebida",
  nut: "Fruto seco",
  other: "Otro",
};

export type Difficulty = "easy" | "medium" | "hard";
export const DIFFICULTY_LABEL_ES: Record<Difficulty, string> = {
  easy: "Fácil",
  medium: "Media",
  hard: "Difícil",
};

export type SourceType = "pdf" | "image" | "text" | "url" | "manual";

export interface IngredientOut {
  id: number;
  name: string;
  category: IngredientCategory;
}

export interface RecipeIngredient {
  ingredient: IngredientOut;
  quantity_raw: string | null;
  quantity_value: number | null;
  quantity_unit: string | null;
  notes: string | null;
  is_pantry: boolean;
}

export interface Step {
  step_number: number;
  title: string | null;
  text: string;
  image_path: string | null;
}

export interface Recipe {
  id: number;
  title: string;
  subtitle: string | null;
  description: string | null;
  servings: number | null;
  total_time_min: number | null;
  cook_time_min: number | null;
  difficulty: Difficulty | null;
  image_path: string | null;
  source_type: SourceType;
  source_ref: string | null;
  created_at: string;
  ingredients: RecipeIngredient[];
  steps: Step[];
  utensils: string[];
  tags: string[];
}

export interface RecipeSummary {
  id: number;
  title: string;
  subtitle: string | null;
  image_path: string | null;
  total_time_min: number | null;
  servings: number | null;
  ingredient_count: number;
  tags: string[];
}

export interface RecipeMatch extends RecipeSummary {
  matched_ingredients: string[];
  missing_ingredients: string[];
}

// Draft returned by /recipes/extract — caller posts back to /recipes
export interface IngredientDraft {
  name: string;
  category: IngredientCategory;
  quantity_raw: string | null;
  is_pantry: boolean;
  notes: string | null;
}

export interface StepDraft {
  title: string | null;
  text: string;
}

export interface RecipeDraft {
  title: string;
  subtitle: string | null;
  description: string | null;
  servings: number | null;
  total_time_min: number | null;
  cook_time_min: number | null;
  difficulty: Difficulty | null;
  ingredients: IngredientDraft[];
  steps: StepDraft[];
  utensils: string[];
  tags: string[];
}
