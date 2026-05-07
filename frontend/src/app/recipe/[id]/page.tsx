import Link from "next/link";
import { notFound } from "next/navigation";
import { api, imageUrl } from "@/lib/api";
import { CATEGORY_LABEL_ES, DIFFICULTY_LABEL_ES } from "@/lib/types";
import { formatTime } from "@/lib/format";

export default async function RecipePage(props: PageProps<"/recipe/[id]">) {
  const { id } = await props.params;
  const recipe = await api.getRecipe(id).catch(() => null);
  if (!recipe) notFound();

  const url = imageUrl(recipe.image_path);
  const fresh = recipe.ingredients.filter((i) => !i.is_pantry);
  const pantry = recipe.ingredients.filter((i) => i.is_pantry);

  return (
    <article className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sm text-accent hover:underline w-fit">
          ← Volver
        </Link>
        <div className="flex gap-2">
          <Link
            href={`/recipe/${recipe.id}/edit`}
            className="px-3 py-1.5 rounded-md border border-border text-sm hover:bg-accent-soft hover:border-accent transition"
          >
            Editar
          </Link>
        </div>
      </div>

      <header className="grid lg:grid-cols-2 gap-8 items-start">
        <div className="aspect-[4/3] rounded-2xl overflow-hidden bg-zinc-100 border border-border">
          {url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt={recipe.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-7xl text-zinc-300">
              🍽️
            </div>
          )}
        </div>
        <div className="flex flex-col gap-3">
          <h1 className="text-3xl font-semibold tracking-tight leading-tight">
            {recipe.title}
          </h1>
          {recipe.subtitle && (
            <p className="text-lg text-muted">{recipe.subtitle}</p>
          )}
          {recipe.description && (
            <p className="text-sm text-foreground/80 leading-relaxed mt-2">
              {recipe.description}
            </p>
          )}
          <dl className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-sm">
            <div>
              <dt className="text-xs uppercase text-muted">Total</dt>
              <dd className="font-medium">{formatTime(recipe.total_time_min)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Cocinado</dt>
              <dd className="font-medium">{formatTime(recipe.cook_time_min)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-muted">Raciones</dt>
              <dd className="font-medium">{recipe.servings}</dd>
            </div>
            {recipe.difficulty && (
              <div>
                <dt className="text-xs uppercase text-muted">Dificultad</dt>
                <dd className="font-medium">{DIFFICULTY_LABEL_ES[recipe.difficulty]}</dd>
              </div>
            )}
          </dl>
          {recipe.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {recipe.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 rounded bg-accent-soft text-accent uppercase tracking-wide"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </header>

      <section className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 flex flex-col gap-6">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
              Ingredientes
            </h2>
            <ul className="flex flex-col gap-1.5 text-sm">
              {fresh.map((i) => (
                <li key={i.ingredient.id} className="flex justify-between gap-2 border-b border-border/60 py-1">
                  <span className="capitalize">
                    {i.ingredient.name}
                    {i.substitutes && (
                      <span className="text-muted text-xs italic"> (o: {i.substitutes})</span>
                    )}
                    {i.notes && (
                      <span className="text-muted text-xs"> · {i.notes}</span>
                    )}
                  </span>
                  <span className="text-muted text-xs whitespace-nowrap">
                    {i.quantity_raw ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
            {pantry.length > 0 && (
              <details className="mt-4">
                <summary className="text-xs text-muted cursor-pointer hover:text-foreground">
                  De tu despensa ({pantry.length})
                </summary>
                <ul className="flex flex-col gap-1.5 text-sm mt-2 pl-4">
                  {pantry.map((i) => (
                    <li key={i.ingredient.id} className="flex justify-between gap-2 text-muted">
                      <span className="capitalize">{i.ingredient.name}</span>
                      <span className="text-xs">{i.quantity_raw ?? "—"}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
          {recipe.utensils.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
                Utensilios
              </h2>
              <ul className="flex flex-col gap-1 text-sm">
                {recipe.utensils.map((u) => (
                  <li key={u} className="capitalize">· {u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="lg:col-span-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Preparación
          </h2>
          <ol className="flex flex-col gap-5">
            {recipe.steps.map((s) => (
              <li key={s.step_number} className="flex gap-4">
                <span className="shrink-0 w-8 h-8 rounded-full bg-accent text-white grid place-items-center text-sm font-semibold">
                  {s.step_number}
                </span>
                <div className="flex-1">
                  {s.title && (
                    <h3 className="font-medium leading-snug mb-1">{s.title}</h3>
                  )}
                  <p className="text-sm text-foreground/85 leading-relaxed">
                    {s.text}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </article>
  );
}
