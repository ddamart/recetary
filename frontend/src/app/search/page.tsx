import Link from "next/link";
import { api, imageUrl } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";
import { formatTime, parseIngredients } from "@/lib/format";

const PAGE_SIZE = 24;

export default async function SearchPage(
  props: PageProps<"/search">,
) {
  const sp = await props.searchParams;
  const q = typeof sp.q === "string" ? sp.q : undefined;
  const ingredientsParam =
    typeof sp.ingredients === "string" ? sp.ingredients : undefined;
  const ingredients = ingredientsParam ? parseIngredients(ingredientsParam) : [];
  const sort = typeof sp.sort === "string" ? sp.sort : undefined;
  const offset = typeof sp.offset === "string" ? Math.max(0, Number(sp.offset) || 0) : 0;

  const isAlpha = sort === "alpha";

  const results = await api
    .search({ q, ingredients, sort, limit: PAGE_SIZE, offset })
    .catch(() => []);

  // Build base query string (without offset) for pagination links
  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  if (ingredientsParam) baseParams.set("ingredients", ingredientsParam);
  if (sort) baseParams.set("sort", sort);

  const prevOffset = offset - PAGE_SIZE;
  const nextOffset = offset + PAGE_SIZE;

  const noFilters = !q && ingredients.length === 0;

  return (
    <div className="flex flex-col gap-6">
      {!isAlpha && (
        <SearchBox initialQuery={q ?? ""} initialIngredients={ingredients} />
      )}

      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">
          {isAlpha && noFilters ? "Todas las recetas" : (
            <>{results.length} {results.length === 1 ? "receta" : "recetas"}</>
          )}
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
          {noFilters
            ? <>Aún no hay recetas. <a href="/add" className="text-accent underline">Añade la primera</a>.</>
            : "Sin resultados. Prueba a quitar algún ingrediente o cambiar el texto."}
        </p>
      ) : isAlpha ? (
        <>
          <ul className="flex flex-col divide-y divide-border">
            {results.map((r) => (
              <li key={r.id} className="flex items-center gap-4 py-3 px-2 -mx-2">
                <Link
                  href={`/recipe/${r.id}`}
                  className="flex items-center gap-4 flex-1 min-w-0 rounded-lg hover:bg-accent-soft transition px-2 py-1 -mx-2"
                >
                  {imageUrl(r.image_path) ? (
                    <img
                      src={imageUrl(r.image_path)!}
                      alt=""
                      className="w-12 h-12 rounded-lg object-cover shrink-0"
                    />
                  ) : (
                    <span className="w-12 h-12 rounded-lg bg-zinc-100 grid place-items-center text-lg shrink-0">
                      🍽
                    </span>
                  )}
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-sm truncate block">
                      {r.title}
                    </span>
                    {r.subtitle && (
                      <span className="text-xs text-muted truncate block">
                        {r.subtitle}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted shrink-0">
                    {r.total_time_min && <span>{formatTime(r.total_time_min)}</span>}
                    <span>{r.ingredient_count} ing.</span>
                  </div>
                </Link>
                <Link
                  href={`/recipe/${r.id}/edit`}
                  className="shrink-0 px-2 py-1.5 rounded-md border border-border text-xs text-muted hover:bg-accent-soft hover:border-accent hover:text-accent transition"
                  title="Editar"
                >
                  Editar
                </Link>
              </li>
            ))}
          </ul>

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
