"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";
import type { RecipeMatch, RecipeSummary } from "@/lib/types";

const PAGE_SIZE = 24;

interface Props {
  initialRecipes: RecipeSummary[];
}

export function SearchableHome({ initialRecipes }: Props) {
  const [results, setResults] = useState<(RecipeSummary | RecipeMatch)[]>(initialRecipes);
  const [searching, setSearching] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(initialRecipes.length >= 12);
  const [hasQuery, setHasQuery] = useState(false);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [sort, setSort] = useState<"recent" | "alpha">("recent");
  const reqId = useRef(0);
  const lastQuery = useRef<{ q?: string; ingredients?: string[]; tag?: string }>({});

  useEffect(() => {
    api.listTags().then(setAvailableTags).catch(() => {});
  }, []);

  const handleChange = useCallback(
    async (q: string, ingredients: string[], tag: string | undefined) => {
      const isEmpty = !q.trim() && ingredients.length === 0 && !tag;
      setHasQuery(!isEmpty);
      lastQuery.current = {
        q: q.trim() || undefined,
        ingredients: ingredients.length ? ingredients : undefined,
        tag,
      };

      if (isEmpty) {
        // Re-fetch with current sort so order is correct
        const id = ++reqId.current;
        try {
          const data = await api.listRecipes({ limit: 12, sort });
          if (id === reqId.current) {
            setResults(data);
            setHasMore(data.length >= 12);
          }
        } catch {
          if (id === reqId.current) {
            setResults(initialRecipes);
            setHasMore(initialRecipes.length >= 12);
          }
        }
        setSearching(false);
        return;
      }

      const id = ++reqId.current;
      setSearching(true);
      try {
        const data = await api.search({
          ...lastQuery.current,
          sort,
          limit: PAGE_SIZE,
          offset: 0,
        });
        if (id === reqId.current) {
          setResults(data);
          setHasMore(data.length >= PAGE_SIZE);
        }
      } catch {
        if (id === reqId.current) {
          setResults([]);
          setHasMore(false);
        }
      } finally {
        if (id === reqId.current) {
          setSearching(false);
        }
      }
    },
    [initialRecipes, sort],
  );

  // Re-fetch when sort order changes
  useEffect(() => {
    const id = ++reqId.current;
    if (hasQuery) {
      api.search({ ...lastQuery.current, sort, limit: PAGE_SIZE, offset: 0 })
        .then((data) => {
          if (id === reqId.current) { setResults(data); setHasMore(data.length >= PAGE_SIZE); }
        })
        .catch(() => {});
    } else {
      api.listRecipes({ limit: 12, sort })
        .then((data) => {
          if (id === reqId.current) { setResults(data); setHasMore(data.length >= 12); }
        })
        .catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      if (hasQuery) {
        const data = await api.search({
          ...lastQuery.current,
          sort,
          limit: PAGE_SIZE,
          offset: results.length,
        });
        setResults((prev) => [...prev, ...data]);
        setHasMore(data.length >= PAGE_SIZE);
      } else {
        const data = await api.listRecipes({
          limit: 12,
          sort,
          offset: results.length,
        });
        setResults((prev) => [...prev, ...data]);
        setHasMore(data.length >= 12);
      }
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  }

  const heading = hasQuery
    ? `${results.length} ${results.length === 1 ? "receta" : "recetas"}`
    : "Recetas";

  return (
    <>
      <div className="w-full max-w-2xl">
        <SearchBox size="lg" availableTags={availableTags} onChange={handleChange} />
      </div>

      <section className="w-full">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {heading}
            {searching && (
              <span className="ml-2 text-sm font-normal text-muted">buscando...</span>
            )}
          </h2>
          <div className="flex items-center gap-2">
            <div className="flex rounded-md border border-border text-xs overflow-hidden">
              <button
                type="button"
                onClick={() => setSort("recent")}
                className={`px-2.5 py-1 transition ${sort === "recent" ? "bg-accent text-white" : "hover:bg-accent-soft"}`}
              >
                Recientes
              </button>
              <button
                type="button"
                onClick={() => setSort("alpha")}
                className={`px-2.5 py-1 transition ${sort === "alpha" ? "bg-accent text-white" : "hover:bg-accent-soft"}`}
              >
                A–Z
              </button>
            </div>
            <span className="text-xs text-muted">{results.length} mostradas</span>
          </div>
        </div>
        {results.length === 0 ? (
          <p className="text-sm text-muted">
            {hasQuery
              ? "Sin resultados. Prueba a quitar algún ingrediente o cambiar el texto."
              : <>Aún no hay recetas. <a href="/add" className="text-accent underline">Añade la primera</a>.</>}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {results.map((r) => (
                <RecipeCard key={r.id} recipe={r} />
              ))}
            </div>
            {hasMore && (
              <div className="flex justify-center mt-6">
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="px-6 py-2 rounded-lg border border-border text-sm font-medium hover:bg-accent-soft hover:border-accent transition disabled:opacity-50"
                >
                  {loadingMore ? "Cargando..." : "Cargar más"}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}
