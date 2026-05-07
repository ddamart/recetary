import Link from "next/link";
import { api } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";
import { parseIngredients } from "@/lib/format";

export default async function SearchPage(
  props: PageProps<"/search">,
) {
  const sp = await props.searchParams;
  const q = typeof sp.q === "string" ? sp.q : undefined;
  const ingredientsParam =
    typeof sp.ingredients === "string" ? sp.ingredients : undefined;
  const ingredients = ingredientsParam ? parseIngredients(ingredientsParam) : [];

  const results = await api
    .search({ q, ingredients, limit: 60 })
    .catch(() => []);

  return (
    <div className="flex flex-col gap-6">
      <SearchBox initialQuery={q ?? ""} initialIngredients={ingredients} />

      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">
          {results.length} {results.length === 1 ? "receta" : "recetas"}
        </h2>
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Inicio
        </Link>
      </div>

      {results.length === 0 ? (
        <p className="text-sm text-muted">
          Sin resultados. Prueba a quitar algún ingrediente o cambiar el texto.
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {results.map((r) => (
            <RecipeCard key={r.id} recipe={r} />
          ))}
        </div>
      )}
    </div>
  );
}
