"use client";

import {
  CATEGORY_LABEL_ES,
  type IngredientCategory,
  type RecipeDraft,
} from "@/lib/types";

const CATEGORIES = Object.keys(CATEGORY_LABEL_ES) as IngredientCategory[];

export interface RecipeFormProps {
  draft: RecipeDraft;
  setDraft: (d: RecipeDraft) => void;
  header: string;
  onBack: () => void;
  backLabel?: string;
  onSubmit: () => void;
  submitLabel?: string;
  busy: boolean;
  error: string | null;
  extraActions?: React.ReactNode;
}

export function RecipeForm({
  draft,
  setDraft,
  header,
  onBack,
  backLabel = "← Atrás",
  onSubmit,
  submitLabel = "Guardar receta",
  busy,
  error,
  extraActions,
}: RecipeFormProps) {
  function patch(p: Partial<RecipeDraft>) {
    setDraft({ ...draft, ...p });
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{header}</h1>
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-muted hover:text-foreground"
        >
          {backLabel}
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
            value={draft.servings ?? ""}
            onChange={(e) =>
              patch({ servings: e.target.value ? Number(e.target.value) : null })
            }
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
                { name: "", category: "other", quantity_raw: "", is_pantry: false, substitutes: null, notes: null },
              ],
            })
          }
        />
        <ul className="flex flex-col gap-2">
          {draft.ingredients.map((ing, i) => (
            <li
              key={i}
              className="grid grid-cols-[1fr_140px_100px_140px_auto_auto] gap-2 items-center"
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
              <input
                value={ing.substitutes ?? ""}
                onChange={(e) =>
                  patch({
                    ingredients: draft.ingredients.map((x, idx) =>
                      idx === i ? { ...x, substitutes: e.target.value || null } : x,
                    ),
                  })
                }
                placeholder="sustitutos"
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
        {extraActions}
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 rounded-md border border-border text-sm hover:bg-zinc-50"
        >
          {backLabel}
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy}
          className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Guardando..." : submitLabel}
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
