// Thin fetch wrapper over the FastAPI backend.

import type {
  IngredientOut, Recipe, RecipeDraft, RecipeMatch, RecipeSummary,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { cache?: RequestCache },
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
    cache: init?.cache ?? "no-store",
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError(response.status, text || response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listRecipes: (params?: { limit?: number; offset?: number; tag?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.tag) qs.set("tag", params.tag);
    const q = qs.toString();
    return request<RecipeSummary[]>(`/recipes${q ? `?${q}` : ""}`);
  },
  getRecipe: (id: number | string) =>
    request<Recipe>(`/recipes/${id}`),
  deleteRecipe: (id: number) =>
    request<void>(`/recipes/${id}`, { method: "DELETE" }),
  randomRecipe: (params?: { ingredients?: string[]; tag?: string }) => {
    const qs = new URLSearchParams();
    if (params?.ingredients?.length) qs.set("ingredients", params.ingredients.join(","));
    if (params?.tag) qs.set("tag", params.tag);
    const q = qs.toString();
    return request<RecipeMatch>(`/recipes/random${q ? `?${q}` : ""}`);
  },
  search: (params: { q?: string; ingredients?: string[]; tag?: string; sort?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.ingredients?.length) qs.set("ingredients", params.ingredients.join(","));
    if (params.tag) qs.set("tag", params.tag);
    if (params.sort) qs.set("sort", params.sort);
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.offset) qs.set("offset", String(params.offset));
    return request<RecipeMatch[]>(`/search?${qs.toString()}`);
  },
  countRecipes: () => request<number>("/recipes/count"),
  listTags: () => request<string[]>("/recipes/tags"),
  listIngredients: (params?: { q?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<IngredientOut[]>(`/ingredients${q ? `?${q}` : ""}`);
  },
  extractDraft: async (form: FormData): Promise<RecipeDraft> =>
    request<RecipeDraft>("/recipes/extract", { method: "POST", body: form }),
  createRecipe: (payload: unknown) =>
    request<Recipe>("/recipes", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRecipe: (id: number, payload: unknown) =>
    request<Recipe>(`/recipes/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};

// Build a full URL for a recipe cover image stored under data/images/.
// Tolerates legacy paths that include a leading "images/" prefix.
export function imageUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  const cleaned = path.replace(/^images\//, "");
  return `${API_URL}/static/images/${cleaned}`;
}
