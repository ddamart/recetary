import { api } from "@/lib/api";
import { SearchableHome } from "@/components/SearchableHome";

export default async function HomePage() {
  const recipes = await api.listRecipes({ limit: 12, sort: "random" }).catch(() => []);

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
        <SearchableHome initialRecipes={recipes} />
      </section>
    </div>
  );
}
