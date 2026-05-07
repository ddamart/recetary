"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  CATEGORY_LABEL_ES,
  type IngredientCategory,
  type RecipeDraft,
} from "@/lib/types";

type SourceKind = "pdf" | "image" | "text" | "url";

const SOURCE_OPTIONS: { kind: SourceKind; label: string; icon: string; help: string }[] = [
  { kind: "pdf", label: "PDF", icon: "📄", help: "Sube un PDF (HelloFresh u otros)" },
  { kind: "image", label: "Imagen", icon: "🖼️", help: "Foto de una receta (PNG/JPG)" },
  { kind: "text", label: "Texto", icon: "✍️", help: "Pega o escribe la receta" },
  { kind: "url", label: "URL", icon: "🔗", help: "Enlace a artículo web" },
];

const CATEGORIES = Object.keys(CATEGORY_LABEL_ES) as IngredientCategory[];

export default function AddPage() {
  const router = useRouter();
  const [source, setSource] = useState<SourceKind>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<RecipeDraft | null>(null);

  async function extract() {
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.set("source_type", source);
      if (source === "pdf" || source === "image") {
        if (!file) throw new Error("Selecciona un fichero");
        form.set("file", file);
      } else if (source === "text") {
        if (!text.trim()) throw new Error("Pega texto de receta");
        form.set("text", text);
      } else {
        if (!url.trim()) throw new Error("Introduce una URL");
        form.set("url", url);
      }
      const result = await api.extractDraft(form);
      setDraft(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!draft) return;
    setError(null);
    setBusy(true);
    try {
      const payload = {
        ...draft,
        source_type: source,
        source_ref:
          source === "url" ? url : source === "text" ? null : file?.name ?? null,
        raw_text: source === "text" ? text : null,
      };
      const created = await api.createRecipe(payload);
      router.push(`/recipe/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      setBusy(false);
    }
  }

  if (draft) {
    return (
      <DraftReview
        draft={draft}
        setDraft={setDraft}
        onBack={() => setDraft(null)}
        onSubmit={commit}
        busy={busy}
        error={error}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Nueva receta</h1>
        <p className="text-sm text-muted">
          Elige el origen, Claude extraerá los ingredientes y los pasos, y revisas
          antes de guardar.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {SOURCE_OPTIONS.map((opt) => (
          <button
            key={opt.kind}
            type="button"
            onClick={() => setSource(opt.kind)}
            className={`flex flex-col items-start gap-1 p-4 rounded-xl border text-left transition ${
              source === opt.kind
                ? "border-accent bg-accent-soft"
                : "border-border bg-card hover:border-accent/40"
            }`}
          >
            <span className="text-2xl">{opt.icon}</span>
            <span className="font-medium text-sm">{opt.label}</span>
            <span className="text-xs text-muted">{opt.help}</span>
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-card p-5">
        {(source === "pdf" || source === "image") && (
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">Fichero</span>
            <input
              type="file"
              accept={source === "pdf" ? ".pdf,application/pdf" : "image/*"}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-accent file:text-white file:cursor-pointer"
            />
            {file && (
              <span className="text-xs text-muted">
                {file.name} · {(file.size / 1024).toFixed(0)} KB
              </span>
            )}
          </label>
        )}
        {source === "text" && (
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">Texto de la receta</span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={10}
              className="border border-border rounded-md p-3 text-sm focus:border-accent outline-none"
              placeholder="Pega aquí la receta en texto plano..."
            />
          </label>
        )}
        {source === "url" && (
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">URL del artículo</span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              className="border border-border rounded-md p-2 text-sm focus:border-accent outline-none"
            />
          </label>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="px-4 py-2 rounded-md border border-border text-sm hover:bg-zinc-50"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={extract}
          disabled={busy}
          className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Extrayendo..." : "Extraer →"}
        </button>
      </div>
    </div>
  );
}

interface ReviewProps {
  draft: RecipeDraft;
  setDraft: (d: RecipeDraft) => void;
  onBack: () => void;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
}

function DraftReview({ draft, setDraft, onBack, onSubmit, busy, error }: ReviewProps) {
  function patch(p: Partial<RecipeDraft>) {
    setDraft({ ...draft, ...p });
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Revisa antes de guardar</h1>
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-muted hover:text-foreground"
        >
          ← Cambiar fuente
        </button>
      </header>

      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Título">
          <input
            value={draft.title}
            onChange={(e) => patch({ title: e.target.value })}
            className="input"
          />
        </Field>
        <Field label="Subtítulo">
          <input
            value={draft.subtitle ?? ""}
            onChange={(e) => patch({ subtitle: e.target.value || null })}
            className="input"
          />
        </Field>
        <Field label="Raciones">
          <input
            type="number"
            min={1}
            max={20}
            value={draft.servings}
            onChange={(e) => patch({ servings: Number(e.target.value) || 2 })}
            className="input w-24"
          />
        </Field>
        <Field label="Tiempo total (min)">
          <input
            type="number"
            value={draft.total_time_min ?? ""}
            onChange={(e) =>
              patch({ total_time_min: e.target.value ? Number(e.target.value) : null })
            }
            className="input w-24"
          />
        </Field>
        <Field label="Tiempo cocinado (min)">
          <input
            type="number"
            value={draft.cook_time_min ?? ""}
            onChange={(e) =>
              patch({ cook_time_min: e.target.value ? Number(e.target.value) : null })
            }
            className="input w-24"
          />
        </Field>
        <Field label="Dificultad">
          <select
            value={draft.difficulty ?? ""}
            onChange={(e) => patch({ difficulty: (e.target.value || null) as RecipeDraft["difficulty"] })}
            className="input"
          >
            <option value="">—</option>
            <option value="easy">Fácil</option>
            <option value="medium">Media</option>
            <option value="hard">Difícil</option>
          </select>
        </Field>
      </div>

      <Field label="Descripción">
        <textarea
          value={draft.description ?? ""}
          onChange={(e) => patch({ description: e.target.value || null })}
          rows={3}
          className="input"
        />
      </Field>

      <section>
        <SectionHead
          title={`Ingredientes (${draft.ingredients.length})`}
          onAdd={() =>
            patch({
              ingredients: [
                ...draft.ingredients,
                { name: "", category: "other", quantity_raw: "", is_pantry: false, notes: null },
              ],
            })
          }
        />
        <ul className="flex flex-col gap-2">
          {draft.ingredients.map((ing, i) => (
            <li
              key={i}
              className="grid grid-cols-[1fr_140px_140px_auto_auto] gap-2 items-center"
            >
              <input
                value={ing.name}
                onChange={(e) =>
                  patch({
                    ingredients: draft.ingredients.map((x, idx) =>
                      idx === i ? { ...x, name: e.target.value } : x,
                    ),
                  })
                }
                placeholder="nombre"
                className="input"
              />
              <select
                value={ing.category}
                onChange={(e) =>
                  patch({
                    ingredients: draft.ingredients.map((x, idx) =>
                      idx === i ? { ...x, category: e.target.value as IngredientCategory } : x,
                    ),
                  })
                }
                className="input"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABEL_ES[c]}
                  </option>
                ))}
              </select>
              <input
                value={ing.quantity_raw ?? ""}
                onChange={(e) =>
                  patch({
                    ingredients: draft.ingredients.map((x, idx) =>
                      idx === i ? { ...x, quantity_raw: e.target.value || null } : x,
                    ),
                  })
                }
                placeholder="cantidad"
                className="input"
              />
              <label className="text-xs flex items-center gap-1 text-muted">
                <input
                  type="checkbox"
                  checked={ing.is_pantry}
                  onChange={(e) =>
                    patch({
                      ingredients: draft.ingredients.map((x, idx) =>
                        idx === i ? { ...x, is_pantry: e.target.checked } : x,
                      ),
                    })
                  }
                />
                despensa
              </label>
              <button
                type="button"
                onClick={() =>
                  patch({
                    ingredients: draft.ingredients.filter((_, idx) => idx !== i),
                  })
                }
                className="text-red-700 text-lg hover:text-red-900"
                aria-label="quitar"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionHead
          title={`Pasos (${draft.steps.length})`}
          onAdd={() =>
            patch({ steps: [...draft.steps, { title: null, text: "" }] })
          }
        />
        <ol className="flex flex-col gap-3">
          {draft.steps.map((step, i) => (
            <li key={i} className="flex gap-3 items-start">
              <span className="shrink-0 w-7 h-7 rounded-full bg-accent text-white grid place-items-center text-xs font-semibold mt-1">
                {i + 1}
              </span>
              <div className="flex-1 flex flex-col gap-1">
                <input
                  value={step.title ?? ""}
                  onChange={(e) =>
                    patch({
                      steps: draft.steps.map((x, idx) =>
                        idx === i ? { ...x, title: e.target.value || null } : x,
                      ),
                    })
                  }
                  placeholder="Título del paso (opcional)"
                  className="input text-sm font-medium"
                />
                <textarea
                  value={step.text}
                  onChange={(e) =>
                    patch({
                      steps: draft.steps.map((x, idx) =>
                        idx === i ? { ...x, text: e.target.value } : x,
                      ),
                    })
                  }
                  rows={3}
                  className="input text-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => patch({ steps: draft.steps.filter((_, idx) => idx !== i) })}
                className="text-red-700 text-lg hover:text-red-900 mt-1"
                aria-label="quitar paso"
              >
                ×
              </button>
            </li>
          ))}
        </ol>
      </section>

      <Field label="Utensilios (separados por coma)">
        <input
          value={draft.utensils.join(", ")}
          onChange={(e) =>
            patch({
              utensils: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          className="input"
        />
      </Field>

      <Field label="Tags (separados por coma)">
        <input
          value={draft.tags.join(", ")}
          onChange={(e) =>
            patch({
              tags: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          className="input"
        />
      </Field>

      {error && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 rounded-md border border-border text-sm hover:bg-zinc-50"
        >
          ← Atrás
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy}
          className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Guardando..." : "Guardar receta"}
        </button>
      </div>

    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium text-xs uppercase text-muted tracking-wide">{label}</span>
      {children}
    </label>
  );
}

function SectionHead({ title, onAdd }: { title: string; onAdd: () => void }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      <button
        type="button"
        onClick={onAdd}
        className="text-xs px-2 py-1 rounded border border-border hover:bg-accent-soft hover:border-accent text-accent"
      >
        + añadir
      </button>
    </div>
  );
}
