"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition, type KeyboardEvent } from "react";

interface Props {
  initialQuery?: string;
  initialIngredients?: string[];
  initialTag?: string;
  availableTags?: string[];
  size?: "lg" | "md";
  onChange?: (q: string, ingredients: string[], tag: string | undefined) => void;
}

export function SearchBox({
  initialQuery = "",
  initialIngredients = [],
  initialTag,
  availableTags = [],
  size = "md",
  onChange,
}: Props) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [ingredients, setIngredients] = useState<string[]>(initialIngredients);
  const [tag, setTag] = useState<string | undefined>(initialTag);
  const [draft, setDraft] = useState("");
  const [isPending, startTransition] = useTransition();

  // Debounced onChange — fires 400ms after the last query/ingredients/tag change.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    if (!onChangeRef.current) return;
    const timer = setTimeout(() => {
      onChangeRef.current!(query, ingredients, tag);
    }, 400);
    return () => clearTimeout(timer);
  }, [query, ingredients, tag]);

  function commitToken(raw: string) {
    const value = raw.trim().toLowerCase();
    if (!value) return;
    if (ingredients.includes(value)) {
      setDraft("");
      return;
    }
    setIngredients([...ingredients, value]);
    setDraft("");
  }

  function removeToken(idx: number) {
    setIngredients(ingredients.filter((_, i) => i !== idx));
  }

  function toggleTag(t: string) {
    setTag(tag === t ? undefined : t);
  }

  function submit() {
    if (onChange) {
      onChange(query, ingredients, tag);
    } else {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (ingredients.length) params.set("ingredients", ingredients.join(","));
      if (tag) params.set("tag", tag);
      startTransition(() => {
        router.push(`/search?${params.toString()}`);
      });
    }
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (draft.trim()) {
        commitToken(draft);
      } else {
        submit();
      }
    }
    if (e.key === "," || e.key === "Tab") {
      if (draft.trim()) {
        e.preventDefault();
        commitToken(draft);
      }
    }
    if (e.key === "Backspace" && !draft && ingredients.length > 0) {
      e.preventDefault();
      setIngredients(ingredients.slice(0, -1));
    }
  }

  const inputClass =
    size === "lg"
      ? "text-base px-4 py-2 min-w-[180px]"
      : "text-sm px-3 py-1.5 min-w-[140px]";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-xl border border-border bg-card focus-within:border-accent transition">
        {ingredients.map((tok, i) => (
          <span
            key={`${tok}-${i}`}
            className="inline-flex items-center gap-1 text-sm px-2 py-1 rounded-md bg-accent-soft text-accent"
          >
            {tok}
            <button
              type="button"
              onClick={() => removeToken(i)}
              className="hover:text-red-700 -mr-1 text-base leading-none"
              aria-label={`quitar ${tok}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKey}
          placeholder={
            ingredients.length === 0
              ? "Empieza a escribir ingredientes (cebolla, tomate, pollo...)"
              : "+ otro ingrediente"
          }
          className={`flex-1 bg-transparent outline-none ${inputClass}`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Filtra por título..."
          className="flex-1 min-w-[200px] px-3 py-2 text-sm rounded-lg border border-border bg-card focus:border-accent outline-none"
        />
        <button
          type="button"
          disabled={isPending}
          onClick={submit}
          className="px-5 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
        >
          {isPending ? "Buscando..." : "Buscar"}
        </button>
      </div>

      {availableTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {availableTags.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => toggleTag(t)}
              className={`text-xs px-2 py-1 rounded-md border transition ${
                tag === t
                  ? "bg-accent text-white border-accent"
                  : "bg-card text-muted border-border hover:border-accent hover:text-accent"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
