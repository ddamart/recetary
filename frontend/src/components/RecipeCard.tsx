import Link from "next/link";
import { imageUrl } from "@/lib/api";
import { formatTime, formatDate } from "@/lib/format";
import type { RecipeMatch, RecipeSummary } from "@/lib/types";

interface Props {
  recipe: RecipeSummary | RecipeMatch;
}

function isMatch(r: RecipeSummary | RecipeMatch): r is RecipeMatch {
  return Array.isArray((r as RecipeMatch).missing_ingredients);
}

export function RecipeCard({ recipe }: Props) {
  const url = imageUrl(recipe.image_path);
  const missing = isMatch(recipe) ? recipe.missing_ingredients : [];
  return (
    <Link
      href={`/recipe/${recipe.id}`}
      className="group rounded-xl overflow-hidden border border-border bg-card hover:shadow-lg hover:border-accent transition flex flex-col"
    >
      <div className="aspect-[4/3] bg-zinc-100 overflow-hidden relative">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={recipe.title}
            className="w-full h-full object-cover group-hover:scale-105 transition"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-300">
            🍽️
          </div>
        )}
      </div>
      <div className="p-4 flex-1 flex flex-col gap-2">
        <h3 className="font-semibold text-sm leading-tight line-clamp-2 min-h-[2.5em]">
          {recipe.title}
        </h3>
        {recipe.subtitle && (
          <p className="text-xs text-muted line-clamp-1">{recipe.subtitle}</p>
        )}
        <div className="flex items-center gap-3 text-xs text-muted mt-auto pt-1">
          <span>⏱ {formatTime(recipe.total_time_min)}</span>
          <span>· {recipe.ingredient_count} ingredientes</span>
          <span className="ml-auto">{formatDate(recipe.created_at)}</span>
        </div>
        {recipe.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {recipe.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="text-[10px] px-1.5 py-0.5 rounded bg-accent-soft text-accent uppercase tracking-wide"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        {missing.length > 0 && (
          <p className="text-[11px] text-muted line-clamp-2">
            <span className="font-medium">También necesitas:</span>{" "}
            {missing.slice(0, 4).join(", ")}
            {missing.length > 4 && `, +${missing.length - 4}`}
          </p>
        )}
      </div>
    </Link>
  );
}
