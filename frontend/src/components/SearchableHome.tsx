"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";
import type { RecipeMatch, RecipeSummary } from "@/lib/types";

const PAGE_SIZE = 24;
const IDLE_PAGE_SIZE = 12;

interface Props {
  initialRecipes: RecipeSummary[];
}

export function SearchableHome({ initialRecipes }: Props) {
  // ── Idle state (random sample, stable across search round-trips) ──
  const idleRecipes = useRef<RecipeSummary[]>(initialRecipes);
  const idleIds = useRef(new Set(initialRecipes.map((r) => r.id)));
  const [idleView, setIdleView] = useState<RecipeSummary[]>(initialRecipes);
  const [idleHasMore, setIdleHasMore] = useState(initialRecipes.length >= IDLE_PAGE_SIZE);
  const [idleLoadingMore, setIdleLoadingMore] = useState(false);

  // ── Search state (completely separate) ──
  const [searchResults, setSearchResults] = useState<RecipeMatch[]>([]);
  const [searchHasMore, setSearchHasMore] = useState(false);
  const [searchLoadingMore, setSearchLoadingMore] = useState(false);
  const [searching, setSearching] = useState(false);
  const [sort, setSort] = useState<"recent" | "alpha">("recent");

  const [hasQuery, setHasQuery] = useState(false);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const reqId = useRef(0);
  const lastQuery = useRef<{ q?: string; ingredients?: string[]; tag?: string }>({});

  useEffect(() => {
    api.listTags().then(setAvailableTags).catch(() => {});
  }, []);

  // ── Search handler (debounced from SearchBox) ──
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
          setSearchResults(data);
          setSearchHasMore(data.length >= PAGE_SIZE);
        }
      } catch {
        if (id === reqId.current) {
          setSearchResults([]);
          setSearchHasMore(false);
        }
      } finally {
        if (id === reqId.current) setSearching(false);
      }
    },
    [sort],
  );

  // Re-fetch search results when sort changes
  useEffect(() => {
    if (!hasQuery) return;
    const id = ++reqId.current;
    api.search({ ...lastQuery.current, sort, limit: PAGE_SIZE, offset: 0 })
      .then((data) => {
        if (id === reqId.current) {
          setSearchResults(data);
          setSearchHasMore(data.length >= PAGE_SIZE);
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort]);

  // ── Load more (idle) ──
  async function loadMoreIdle() {
    setIdleLoadingMore(true);
    try {
      const data = await api.listRecipes({
        limit: IDLE_PAGE_SIZE,
        sort: "recent",
        offset: idleRecipes.current.length,
      });
      // Deduplicate against the random initial batch
      const fresh = data.filter((r) => !idleIds.current.has(r.id));
      for (const r of fresh) idleIds.current.add(r.id);
      idleRecipes.current = [...idleRecipes.current, ...fresh];
      setIdleView(idleRecipes.current);
      setIdleHasMore(data.length >= IDLE_PAGE_SIZE);
    } catch {
      setIdleHasMore(false);
    } finally {
      setIdleLoadingMore(false);
    }
  }

  // ── Load more (search) ──
  async function loadMoreSearch() {
    setSearchLoadingMore(true);
    try {
      const data = await api.search({
        ...lastQuery.current,
        sort,
        limit: PAGE_SIZE,
        offset: searchResults.length,
      });
      setSearchResults((prev) => [...prev, ...data]);
      setSearchHasMore(data.length >= PAGE_SIZE);
    } catch {
      setSearchHasMore(false);
    } finally {
      setSearchLoadingMore(false);
    }
  }

  // ── Render ──
  const results = hasQuery ? searchResults : idleView;
  const hasMore = hasQuery ? searchHasMore : idleHasMore;
  const loadingMore = hasQuery ? searchLoadingMore : idleLoadingMore;
  const loadMore = hasQuery ? loadMoreSearch : loadMoreIdle;

  const heading = hasQuery
    ? `${searchResults.length} ${searchResults.length === 1 ? "receta" : "recetas"}`
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
          {hasQuery && (
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
              <span className="text-xs text-muted">{searchResults.length} mostradas</span>
            </div>
          )}
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
