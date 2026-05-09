"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, imageUrl } from "@/lib/api";
import { recipeToDraft } from "@/lib/convert";
import { RecipeForm } from "@/components/RecipeForm";
import type { Recipe, RecipeDraft } from "@/lib/types";

export default function EditRecipePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [imageBlob, setImageBlob] = useState<Blob | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageStyles, setImageStyles] = useState<{ id: string; label: string }[]>([]);
  const [selectedStyle, setSelectedStyle] = useState("ghibli");

  useEffect(() => {
    api
      .getRecipe(id)
      .then((r) => {
        setRecipe(r);
        setDraft(recipeToDraft(r));
      })
      .catch(() => setError("No se pudo cargar la receta"))
      .finally(() => setLoading(false));
    api.getImageStyles().then(setImageStyles).catch(() => {});
  }, [id]);

  const regenerateImage = useCallback(async (style?: string) => {
    if (!draft) return;
    setImageLoading(true);
    setImageError(null);
    try {
      const blob = await api.generateImage(draft.title, draft.subtitle, style);
      setImageBlob(blob);
      await api.uploadImage(id, blob);
    } catch (e: unknown) {
      if (e instanceof Error && "status" in e && (e as { status: number }).status === 429) {
        setImageError(e.message || "Límite de generación de imágenes alcanzado.");
      }
    } finally {
      setImageLoading(false);
    }
  }, [draft, id]);

  async function save() {
    if (!draft || !recipe) return;
    setError(null);
    setBusy(true);
    try {
      const payload = {
        ...draft,
        source_type: recipe.source_type,
        source_ref: recipe.source_ref,
        raw_text: null,
        image_path: recipe.image_path,
      };
      await api.updateRecipe(id, payload);
      router.push(`/recipe/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar");
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!confirm("¿Eliminar esta receta? Esta acción no se puede deshacer.")) return;
    setBusy(true);
    try {
      await api.deleteRecipe(id);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar");
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted py-12 text-center">Cargando receta...</p>;
  }

  if (!draft) {
    return (
      <p className="text-sm text-red-700 py-12 text-center">
        {error || "Receta no encontrada"}
      </p>
    );
  }

  return (
    <RecipeForm
      draft={draft}
      setDraft={setDraft}
      header={`Editar: ${recipe?.title ?? ""}`}
      onBack={() => router.push(`/recipe/${id}`)}
      backLabel="← Volver"
      onSubmit={save}
      submitLabel="Guardar cambios"
      busy={busy}
      error={error}
      imageBlob={imageBlob}
      imageUrl={imageUrl(recipe?.image_path)}
      imageLoading={imageLoading}
      imageError={imageError}
      onDismissImageError={() => setImageError(null)}
      onRegenerateImage={() => regenerateImage(selectedStyle)}
      imageStyles={imageStyles}
      selectedStyle={selectedStyle}
      onStyleChange={(s) => { setSelectedStyle(s); regenerateImage(s); }}
      extraActions={
        <button
          type="button"
          onClick={handleDelete}
          disabled={busy}
          className="px-4 py-2 rounded-md border border-red-300 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50 mr-auto"
        >
          Eliminar
        </button>
      }
    />
  );
}
