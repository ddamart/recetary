"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export function RegenerateImageButton({
  recipeId,
  title,
  description,
}: {
  recipeId: number;
  title: string;
  description: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function regenerate() {
    setBusy(true);
    try {
      const blob = await api.generateImage(title, description);
      await api.uploadImage(recipeId, blob);
      router.refresh();
    } catch {
      // non-blocking
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={regenerate}
      disabled={busy}
      className="px-3 py-1.5 rounded-md border border-border text-sm hover:bg-accent-soft hover:border-accent transition disabled:opacity-50"
    >
      {busy ? "Generando..." : "Regenerar imagen"}
    </button>
  );
}
