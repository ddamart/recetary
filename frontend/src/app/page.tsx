import { api } from "@/lib/api";
import { RecipeCard } from "@/components/RecipeCard";
import { SearchBox } from "@/components/SearchBox";

export default async function HomePage() {
  const recipes = await api.listRecipes({ limit: 12 }).catch(() => []);

  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col items-center text-center gap-6 py-8">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight max-w-2xl">
          ¿Qué tienes hoy en la nevera?
        </h1>
        <p className="text-muted max-w-xl text-sm">
          Añade los ingredientes que tengas y te enseño qué puedes cocinar.
          También puedes filtrar por título o pedir una receta al azar.
        </p>
        <div className="w-full max-w-2xl">
          <SearchBox size="lg" />
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-lg font-semibold">Recetas recientes</h2>
          <span className="text-xs text-muted">{recipes.length} mostradas</span>
        </div>
        {recipes.length === 0 ? (
          <p className="text-sm text-muted">
            Aún no hay recetas. <a href="/add" className="text-accent underline">Añade la primera</a>.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {recipes.map((r) => (
              <RecipeCard key={r.id} recipe={r} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
