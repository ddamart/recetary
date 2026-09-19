// Thin fetch wrapper over the FastAPI backend.

import type {
  IngredientOut, Recipe, RecipeDraft, RecipeMatch, RecipeSummary, VideoRecipeList,
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
    let message = text || response.statusText;
    try {
      const body = JSON.parse(text);
      message = typeof body.detail === "string"
        ? body.detail
        : body.detail?.message ?? message;
    } catch {
      // Keep the raw response when it is not JSON.
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listRecipes: (params?: { limit?: number; offset?: number; tag?: string; sort?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.tag) qs.set("tag", params.tag);
    if (params?.sort) qs.set("sort", params.sort);
    const q = qs.toString();
    return request<RecipeSummary[]>(`/recipes${q ? `?${q}` : ""}`);
  },
  getRecipe: (id: string) =>
    request<Recipe>(`/recipes/${id}`),
  deleteRecipe: (id: string) =>
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
  checkSource: (url: string) => {
    const qs = new URLSearchParams({ url });
    return request<{ duplicate: boolean; recipe_id?: string; title?: string }>(
      `/recipes/source-check?${qs.toString()}`,
    );
  },
  listIngredients: (params?: { q?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<IngredientOut[]>(`/ingredients${q ? `?${q}` : ""}`);
  },
  extractDraft: async (form: FormData): Promise<RecipeDraft> =>
    request<RecipeDraft>("/recipes/extract", { method: "POST", body: form }),
  listVideoRecipes: async (url: string): Promise<VideoRecipeList> => {
    const form = new FormData();
    form.set("url", url);
    return request<VideoRecipeList>("/recipes/list-video-recipes", { method: "POST", body: form });
  },
  getInfo: () => request<{ extractor_backend: string }>("/info"),
  getImageStyles: () => request<{ id: string; label: string }[]>("/recipes/image-styles"),
  generateImage: async (title: string, subtitle: string | null, description: string | null, style?: string, referenceImage?: Blob | null): Promise<Blob> => {
    const form = new FormData();
    form.set("title", title);
    if (subtitle) form.set("subtitle", subtitle);
    if (description) form.set("description", description);
    if (style) form.set("style", style);
    if (referenceImage) form.set("reference_image", referenceImage, "reference.jpg");
    const res = await fetch(`${API_URL}/recipes/generate-image`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
      } catch {
        // fall back to statusText
      }
      throw new ApiError(res.status, detail);
    }
    return res.blob();
  },
  uploadImage: async (recipeId: string, blob: Blob): Promise<{ image_path: string }> => {
    const form = new FormData();
    form.append("file", blob, `${recipeId}.png`);
    return request<{ image_path: string }>(`/recipes/${recipeId}/image`, {
      method: "POST",
      body: form,
    });
  },
  createRecipe: (payload: unknown) =>
    request<Recipe>("/recipes", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRecipe: (id: string, payload: unknown) =>
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
