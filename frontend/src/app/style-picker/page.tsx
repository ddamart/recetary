"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";

interface RecipeSummary {
  id: string;
  title: string;
  image_path: string | null;
}

interface Progress {
  running: boolean;
  total: number;
  done: number;
  current: {
    recipe_id: string;
    recipe_title: string;
    style: string;
    index: number;
  } | null;
  errors: number;
  stop_requested: boolean;
}

interface RecipeVariants {
  recipe_id: string;
  variants: Record<string, (string | null)[]>;
}

interface StyleDef {
  id: string;
  label: string;
}

function variantUrl(path: string): string {
  return `${API_URL}/static/style-variants/${path}`;
}

function recipeImageUrl(path: string | null): string | null {
  if (!path) return null;
  const cleaned = path.replace(/^images\//, "");
  return `${API_URL}/static/images/${cleaned}`;
}

async function fetchAllRecipes(): Promise<RecipeSummary[]> {
  const [page1, page2] = await Promise.all([
    fetch(`${API_URL}/recipes?limit=100&offset=0`).then((r) => r.json()),
    fetch(`${API_URL}/recipes?limit=100&offset=100`).then((r) => r.json()),
  ]);
  return [...(page1 as RecipeSummary[]), ...(page2 as RecipeSummary[])];
}

export default function StylePickerPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [styles, setStyles] = useState<StyleDef[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeStyle, setActiveStyle] = useState<string>("");
  const [variants, setVariants] = useState<RecipeVariants | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loadingRecipes, setLoadingRecipes] = useState(true);
  const [loadingVariants, setLoadingVariants] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null);
  const progressPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const variantPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchProgress = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/style-variants/progress`);
      if (res.ok) setProgress(await res.json());
    } catch {}
  }, []);

  const loadVariants = useCallback(async (recipeId: string) => {
    try {
      const res = await fetch(`${API_URL}/style-variants/${recipeId}`);
      if (res.ok) setVariants(await res.json());
    } finally {
      setLoadingVariants(false);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    fetchAllRecipes()
      .then((r) => {
        setRecipes(r);
        setLoadingRecipes(false);
      })
      .catch(() => setLoadingRecipes(false));

    fetch(`${API_URL}/recipes/image-styles`)
      .then((r) => r.json())
      .then((s: StyleDef[]) => {
        setStyles(s);
        if (s.length > 0) setActiveStyle(s[0].id);
      })
      .catch(() => {});

    fetchProgress();
  }, [fetchProgress]);

  // Poll progress while running
  useEffect(() => {
    if (progress?.running) {
      progressPollRef.current = setInterval(fetchProgress, 3000);
    } else {
      if (progressPollRef.current) {
        clearInterval(progressPollRef.current);
        progressPollRef.current = null;
      }
    }
    return () => {
      if (progressPollRef.current) clearInterval(progressPollRef.current);
    };
  }, [progress?.running, fetchProgress]);

  // Load variants when recipe is selected
  useEffect(() => {
    if (selectedId) {
      setLoadingVariants(true);
      setVariants(null);
      loadVariants(selectedId);
    }
  }, [selectedId, loadVariants]);

  // Poll variants of selected recipe while generating
  useEffect(() => {
    if (progress?.running && selectedId) {
      variantPollRef.current = setInterval(
        () => loadVariants(selectedId),
        5000,
      );
    } else {
      if (variantPollRef.current) {
        clearInterval(variantPollRef.current);
        variantPollRef.current = null;
      }
    }
    return () => {
      if (variantPollRef.current) clearInterval(variantPollRef.current);
    };
  }, [progress?.running, selectedId, loadVariants]);

  const handleStart = async () => {
    if (!selectedId || progress?.running) return;
    await fetch(`${API_URL}/style-variants/start/${selectedId}`, {
      method: "POST",
    });
    setTimeout(fetchProgress, 600);
  };

  const handleStop = async () => {
    await fetch(`${API_URL}/style-variants/stop`, { method: "POST" });
    setTimeout(fetchProgress, 600);
  };

  const handleSelect = async (style: string, index: number) => {
    if (!selectedId) return;
    const key = `${style}/${index}`;
    setSelecting(key);
    try {
      const res = await fetch(
        `${API_URL}/style-variants/${selectedId}/${style}/${index}/select`,
        { method: "POST" },
      );
      if (res.ok) {
        setRecipes((prev) =>
          prev.map((r) =>
            r.id === selectedId
              ? { ...r, image_path: `${selectedId}.png` }
              : r,
          ),
        );
      }
    } finally {
      setSelecting(null);
    }
  };

  const selectedRecipe = recipes.find((r) => r.id === selectedId);
  const currentSlots = variants?.variants[activeStyle] ?? [];
  const pct =
    progress && progress.total > 0
      ? Math.round((progress.done / progress.total) * 100)
      : 0;
  const isCurrentRecipe = progress?.current?.recipe_id === selectedId;

  return (
    <div className="flex flex-col gap-6">
      {/* Progress bar */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <h1 className="font-semibold text-base shrink-0">
            Selector de estilos
          </h1>
          <div className="flex-1 flex items-center gap-3 min-w-0">
            <div className="w-full max-w-xs bg-border rounded-full h-2 shrink-0">
              <div
                className="bg-accent h-2 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-muted shrink-0">
              {progress ? `${progress.done} / ${progress.total}` : "–"}
              {progress && progress.errors > 0
                ? ` · ${progress.errors} errores`
                : ""}
            </span>
            {progress?.current && (
              <span className="text-xs text-muted truncate hidden sm:block">
                {progress.current.recipe_title} · {progress.current.style} #{progress.current.index}
              </span>
            )}
          </div>
          <div className="flex gap-2 shrink-0">
            {progress?.running ? (
              <button
                onClick={handleStop}
                className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent-soft transition"
              >
                Detener
              </button>
            ) : (
              <button
                onClick={handleStart}
                disabled={!selectedId}
                className="px-3 py-1.5 text-sm rounded-md bg-accent text-white hover:opacity-90 transition disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {selectedId ? "Generar receta seleccionada" : "Selecciona una receta"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="flex gap-6">
        {/* Recipe sidebar */}
        <div className="w-72 shrink-0 rounded-lg border border-border overflow-hidden sticky top-14 self-start max-h-[calc(100vh-5rem)] flex flex-col">
          <div className="px-3 py-2 border-b border-border bg-card text-xs font-medium text-muted shrink-0">
            {loadingRecipes ? "Cargando..." : `${recipes.length} recetas`}
          </div>
          <div className="overflow-y-auto flex-1">
            {recipes.map((recipe) => {
              const isGenerating =
                progress?.current?.recipe_id === recipe.id;
              const isSelected = selectedId === recipe.id;
              return (
                <button
                  key={recipe.id}
                  onClick={() => setSelectedId(recipe.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left border-b border-border transition text-sm ${
                    isSelected
                      ? "bg-accent-soft border-l-2 border-l-accent"
                      : "hover:bg-accent-soft"
                  }`}
                >
                  <div className="w-9 h-9 rounded shrink-0 overflow-hidden bg-border flex items-center justify-center">
                    {recipe.image_path ? (
                      <img
                        src={recipeImageUrl(recipe.image_path)!}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-base">🍽️</span>
                    )}
                  </div>
                  <span className="truncate flex-1 leading-tight">
                    {recipe.title}
                  </span>
                  {isGenerating && (
                    <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Variant viewer */}
        <div className="flex-1 min-w-0">
          {!selectedId ? (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-border h-64 text-muted text-sm">
              Selecciona una receta para ver sus variantes
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <h2 className="text-xl font-semibold leading-tight">
                {selectedRecipe?.title}
              </h2>

              {/* Style tabs */}
              <div className="flex gap-1.5 flex-wrap">
                {styles.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => setActiveStyle(style.id)}
                    className={`px-3 py-1.5 text-sm rounded-md border transition ${
                      activeStyle === style.id
                        ? "bg-accent text-white border-accent"
                        : "border-border hover:bg-accent-soft hover:border-accent"
                    }`}
                  >
                    {style.label}
                  </button>
                ))}
              </div>

              {/* Variant grid */}
              {loadingVariants && !variants ? (
                <div className="grid grid-cols-5 gap-3">
                  {Array.from({ length: 10 }, (_, i) => (
                    <div
                      key={i}
                      className="aspect-square rounded-lg bg-border animate-pulse"
                    />
                  ))}
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-5 gap-3">
                    {Array.from({ length: 10 }, (_, idx) => {
                      const path = currentSlots[idx] ?? null;
                      return (
                        <div key={idx} className="group relative">
                          {path ? (
                            <>
                              <img
                                src={variantUrl(path)}
                                alt={`Variante ${idx + 1}`}
                                className="w-full aspect-square object-cover rounded-lg border border-border"
                              />
                              <div className="absolute inset-0 rounded-lg bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-end justify-center pb-2">
                                <button
                                  onClick={() =>
                                    handleSelect(activeStyle, idx)
                                  }
                                  disabled={
                                    selecting === `${activeStyle}/${idx}`
                                  }
                                  className="px-2.5 py-1 text-xs font-semibold bg-white text-black rounded hover:bg-accent hover:text-white transition disabled:opacity-50"
                                >
                                  {selecting === `${activeStyle}/${idx}`
                                    ? "..."
                                    : "Usar esta"}
                                </button>
                              </div>
                              <span className="absolute top-1 left-1 bg-black/60 text-white text-[10px] rounded px-1 leading-4">
                                {idx + 1}
                              </span>
                            </>
                          ) : (
                            <div className="w-full aspect-square rounded-lg border border-dashed border-border bg-background flex items-center justify-center text-muted">
                              {isCurrentRecipe &&
                              progress?.current?.style === activeStyle ? (
                                <span className="text-xs animate-pulse">
                                  Generando...
                                </span>
                              ) : (
                                <span className="text-2xl opacity-30">⏳</span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-muted">
                    {currentSlots.filter(Boolean).length} / 10 variantes
                    generadas para este estilo
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
