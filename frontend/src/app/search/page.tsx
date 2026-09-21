import Link from "next/link";
import { api, imageUrl } from "@/lib/api";
import { SearchBox } from "@/components/SearchBox";
import { formatTime, parseIngredients } from "@/lib/format";

const DEFAULT_PAGE_SIZE = 24;
const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];

export default async function SearchPage(
  props: PageProps<"/search">,
) {
  const sp = await props.searchParams;
  const q = typeof sp.q === "string" ? sp.q : undefined;
  const ingredientsParam =
    typeof sp.ingredients === "string" ? sp.ingredients : undefined;
  const ingredients = ingredientsParam ? parseIngredients(ingredientsParam) : [];
  const tag = typeof sp.tag === "string" ? sp.tag : undefined;
  const sort = typeof sp.sort === "string" ? sp.sort : undefined;
  const pageSize =
    typeof sp.size === "string" && PAGE_SIZE_OPTIONS.includes(Number(sp.size))
      ? Number(sp.size)
      : DEFAULT_PAGE_SIZE;
  const page = typeof sp.page === "string" ? Math.max(1, Number(sp.page) || 1) : 1;
  const offset = (page - 1) * pageSize;

  const [results, totalCount, availableTags] = await Promise.all([
    api.search({ q, ingredients, tag, sort, limit: pageSize, offset }).catch(() => []),
    api.countSearchResults({ q, ingredients, tag }).catch(() => 0),
    api.listTags().catch(() => []),
  ]);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  // Build base query string (without page) for pagination links
  const baseParams = new URLSearchParams();
  if (q) baseParams.set("q", q);
  if (ingredientsParam) baseParams.set("ingredients", ingredientsParam);
  if (sort) baseParams.set("sort", sort);
  if (tag) baseParams.set("tag", tag);
  if (pageSize !== DEFAULT_PAGE_SIZE) baseParams.set("size", String(pageSize));

  function pageUrl(p: number) {
    const params = new URLSearchParams(baseParams);
    if (p > 1) params.set("page", String(p));
    return `/search?${params.toString()}`;
  }

  function sizeUrl(s: number) {
    const params = new URLSearchParams(baseParams);
    params.set("size", String(s));
    params.delete("page");
    return `/search?${params.toString()}`;
  }

  const noFilters = !q && ingredients.length === 0 && !tag;

  // Sort toggle URLs
  const sortParams = (s: string) => {
    const p = new URLSearchParams(baseParams);
    p.set("sort", s);
    p.delete("page");
    return `/search?${p.toString()}`;
  };

  return (
    <div className="flex flex-col gap-6">
      <SearchBox
        initialQuery={q ?? ""}
        initialIngredients={ingredients}
        initialTag={tag}
        availableTags={availableTags}
      />

      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">
          {noFilters ? "Todas las recetas" : (
            <>{results.length} {results.length === 1 ? "receta" : "recetas"}</>
          )}
          {totalCount > 0 && (
            <span className="text-sm font-normal text-muted ml-2">
              ({totalCount} total)
            </span>
          )}
        </h2>
        <div className="flex items-center gap-3">
          <div className="flex rounded-md border border-border text-xs overflow-hidden">
            <Link
              href={sortParams("recent")}
              className={`px-2.5 py-1 transition ${sort !== "alpha" ? "bg-accent text-white" : "hover:bg-accent-soft"}`}
            >
              Recientes
            </Link>
            <Link
              href={sortParams("alpha")}
              className={`px-2.5 py-1 transition ${sort === "alpha" ? "bg-accent text-white" : "hover:bg-accent-soft"}`}
            >
              A–Z
            </Link>
          </div>
          <Link href="/" className="text-sm text-accent hover:underline">
            ← Inicio
          </Link>
        </div>
      </div>

      {results.length === 0 && page === 1 ? (
        <p className="text-sm text-muted">
          {noFilters
            ? <>Aún no hay recetas. <a href="/add" className="text-accent underline">Añade la primera</a>.</>
            : "Sin resultados. Prueba a quitar algún ingrediente o cambiar el texto."}
        </p>
      ) : (
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
                    {r.match_provenance.length > 0 && (
                      <span className="text-[11px] text-muted truncate block">
                        {r.match_provenance.map((match) =>
                          match.match_type === "canonical"
                            ? match.ingredient
                            : `${match.ingredient} (${match.match_type === "alias" ? "alias" : "familia"})`,
                        ).join(", ")}
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

          {/* Page size selector + numbered pagination */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-2">
            <div className="flex items-center gap-2 text-sm text-muted">
              <span>Mostrar</span>
              {PAGE_SIZE_OPTIONS.map((s) => (
                <Link
                  key={s}
                  href={sizeUrl(s)}
                  className={`px-2 py-1 rounded-md border text-xs transition ${
                    s === pageSize
                      ? "bg-accent text-white border-accent"
                      : "border-border hover:border-accent hover:text-accent"
                  }`}
                >
                  {s}
                </Link>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                {page > 1 && (
                  <Link
                    href={pageUrl(page - 1)}
                    className="px-2 py-1 rounded-md border border-border text-xs hover:bg-accent-soft hover:border-accent transition"
                  >
                    ←
                  </Link>
                )}
                {pageNumbers(page, totalPages).map((p, i) =>
                  p === null ? (
                    <span key={`gap-${i}`} className="px-1 text-xs text-muted">...</span>
                  ) : (
                    <Link
                      key={p}
                      href={pageUrl(p)}
                      className={`px-2.5 py-1 rounded-md border text-xs transition ${
                        p === page
                          ? "bg-accent text-white border-accent"
                          : "border-border hover:bg-accent-soft hover:border-accent"
                      }`}
                    >
                      {p}
                    </Link>
                  ),
                )}
                {page < totalPages && (
                  <Link
                    href={pageUrl(page + 1)}
                    className="px-2 py-1 rounded-md border border-border text-xs hover:bg-accent-soft hover:border-accent transition"
                  >
                    →
                  </Link>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** Generate page numbers with ellipsis gaps. Always shows first, last, and ±1 around current. */
function pageNumbers(current: number, total: number): (number | null)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = new Set<number>();
  pages.add(1);
  pages.add(total);
  for (let i = Math.max(1, current - 1); i <= Math.min(total, current + 1); i++) {
    pages.add(i);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | null)[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) {
      result.push(null);
    }
    result.push(sorted[i]);
  }
  return result;
}
