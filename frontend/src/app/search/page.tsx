import Link from "next/link";
import { api } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";
import { parseIngredients } from "@/lib/format";

const PAGE_SIZE = 24;

export default async function SearchPage(
  props: PageProps<"/search">,
) {
  const sp = await props.searchParams;
  const q = typeof sp.q === "string" ? sp.q : undefined;
  const ingredientsParam =
    typeof sp.ingredients === "string" ? sp.ingredients : undefined;
  const ingredients = ingredientsParam ? parseIngredients(ingredientsParam) : [];
  const offset = typeof sp.offset === "string" ? Math.max(0, Number(sp.offset) || 0) : 0;

  const results = await api
    .search({ q, ingredients, limit: PAGE_SIZE, offset })
    .catch(() => []);

  // Build base query string (without offset) for pagination links
  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  if (ingredientsParam) baseParams.set("ingredients", ingredientsParam);

  const prevOffset = offset - PAGE_SIZE;
  const nextOffset = offset + PAGE_SIZE;

  return (
    <div className="flex flex-col gap-6">
      <SearchBox initialQuery={q ?? ""} initialIngredients={ingredients} />

      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">
          {results.length} {results.length === 1 ? "receta" : "recetas"}
          {offset > 0 && (
            <span className="text-sm font-normal text-muted ml-2">
              (desde {offset + 1})
            </span>
          )}
        </h2>
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Inicio
        </Link>
      </div>

      {results.length === 0 && offset === 0 ? (
        <p className="text-sm text-muted">
          Sin resultados. Prueba a quitar algún ingrediente o cambiar el texto.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {results.map((r) => (
              <RecipeCard key={r.id} recipe={r} />
            ))}
          </div>

          <div className="flex justify-center gap-3 mt-2">
            {prevOffset >= 0 && (
              <Link
                href={`/search?${(() => { const p = new URLSearchParams(baseParams); if (prevOffset > 0) p.set("offset", String(prevOffset)); return p.toString(); })()}`}
                className="px-5 py-2 rounded-lg border border-border text-sm font-medium hover:bg-accent-soft hover:border-accent transition"
              >
                ← Anterior
              </Link>
            )}
            {results.length >= PAGE_SIZE && (
              <Link
                href={`/search?${(() => { const p = new URLSearchParams(baseParams); p.set("offset", String(nextOffset)); return p.toString(); })()}`}
                className="px-5 py-2 rounded-lg border border-border text-sm font-medium hover:bg-accent-soft hover:border-accent transition"
              >
                Siguiente →
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  );
}
