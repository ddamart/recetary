"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RecipeForm } from "@/components/RecipeForm";
import type { RecipeDraft } from "@/lib/types";

type SourceKind = "pdf" | "image" | "text" | "url" | "video";

const SOURCE_OPTIONS: { kind: SourceKind; label: string; icon: string; help: string }[] = [
  { kind: "pdf", label: "PDF", icon: "📄", help: "Sube un PDF (HelloFresh u otros)" },
  { kind: "image", label: "Imagen", icon: "🖼️", help: "Foto de una receta (PNG/JPG)" },
  { kind: "text", label: "Texto", icon: "✍️", help: "Pega o escribe la receta" },
  { kind: "url", label: "URL", icon: "🔗", help: "Enlace a artículo web" },
  { kind: "video", label: "Vídeo", icon: "🎬", help: "YouTube, Instagram o Twitter/X" },
];

function isTwitterUrl(url: string): boolean {
  return /(?:twitter\.com|x\.com)\/\w+\/status\/\d+/.test(url);
}

export default function AddPage() {
  const router = useRouter();
  const [source, setSource] = useState<SourceKind>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [backend, setBackend] = useState<string>("gemini");
  const [imageBlob, setImageBlob] = useState<Blob | null>(null);
  const [imageLoading, setImageLoading] = useState(false);

  useEffect(() => {
    api.getInfo().then((info) => setBackend(info.extractor_backend)).catch(() => {});
  }, []);

  const twitterBlocked = source === "video" && isTwitterUrl(url) && backend !== "gemini";

  // Auto-generate image when draft is set
  const generateImage = useCallback(async (title: string, subtitle: string | null) => {
    setImageLoading(true);
    setError(null);
    try {
      const blob = await api.generateImage(title, subtitle);
      setImageBlob(blob);
    } catch (e: unknown) {
      if (e instanceof Error && "status" in e && (e as { status: number }).status === 429) {
        setError(e.message || "Límite de generación de imágenes alcanzado.");
      }
      // Other image errors are non-blocking
    } finally {
      setImageLoading(false);
    }
  }, []);

  useEffect(() => {
    if (draft) {
      generateImage(draft.title, draft.subtitle);
    }
  }, [draft?.title]); // eslint-disable-line react-hooks/exhaustive-deps

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
          source === "url" || source === "video"
            ? url
            : source === "text" ? null : file?.name ?? null,
        raw_text: source === "text" ? text : null,
      };
      const created = await api.createRecipe(payload);
      if (imageBlob) {
        try { await api.uploadImage(created.id, imageBlob); } catch {}
      }
      router.push(`/recipe/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      setBusy(false);
    }
  }

  if (draft) {
    return (
      <RecipeForm
        draft={draft}
        setDraft={setDraft}
        header="Revisa antes de guardar"
        onBack={() => { setDraft(null); setImageBlob(null); }}
        backLabel="← Cambiar fuente"
        onSubmit={commit}
        busy={busy}
        error={error}
        imageBlob={imageBlob}
        imageLoading={imageLoading}
        onRegenerateImage={() => generateImage(draft.title, draft.subtitle)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Nueva receta</h1>
        <p className="text-sm text-muted">
          Elige el origen, la IA extraerá los ingredientes y los pasos, y revisas
          antes de guardar.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
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
        {source === "video" && (
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">URL del vídeo</span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtube.com/watch?v=... · instagram.com/reel/... · x.com/.../status/..."
              className="border border-border rounded-md p-2 text-sm focus:border-accent outline-none"
            />
            <span className="text-xs text-muted">
              YouTube (subtítulos), Instagram (texto del post) y Twitter/X (vídeo)
            </span>
            {twitterBlocked && (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
                Los vídeos de Twitter/X requieren el backend Gemini.
                El backend actual (Claude) no admite procesamiento de vídeo directo.
              </p>
            )}
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
          disabled={busy || twitterBlocked}
          className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Extrayendo..." : "Extraer →"}
        </button>
      </div>
    </div>
  );
}
