import { redirect } from "next/navigation";
import { api } from "@/lib/api";

export default async function RandomPage() {
  try {
    const match = await api.randomRecipe();
    redirect(`/recipe/${match.id}`);
  } catch (e) {
    // Re-throw redirect errors so Next.js handles them properly
    if (e && typeof e === "object" && "digest" in e) throw e;
    return (
      <p className="text-sm text-muted">
        No hay recetas todavía. Añade la primera para usar Random.
      </p>
    );
  }
}
