"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RecipeForm } from "@/components/RecipeForm";
import type { RecipeDraft, VideoRecipeItem } from "@/lib/types";

type SourceKind = "pdf" | "image" | "text" | "url" | "video";
type PageView = "source" | "picker" | "flow";

const SOURCE_OPTIONS: { kind: SourceKind; label: string; icon: string; help: string }[] = [
  { kind: "pdf",   label: "PDF",    icon: "📄", help: "Sube un PDF (HelloFresh u otros)" },
  { kind: "image", label: "Imagen", icon: "🖼️", help: "Foto de una receta (PNG/JPG)" },
  { kind: "text",  label: "Texto",  icon: "✍️", help: "Pega o escribe la receta" },
  { kind: "url",   label: "URL",    icon: "🔗", help: "Enlace a artículo web" },
  { kind: "video", label: "Vídeo",  icon: "🎬", help: "YouTube, Instagram o Twitter/X" },
];

function isTwitterUrl(url: string)   { return /(?:twitter\.com|x\.com)\/\w+\/status\/\d+/.test(url); }
function isInstagramUrl(url: string) { return /instagram\.com\/(?:[^/?#]+\/)?(?:reel|reels|p)\/[\w-]+/.test(url); }
function isYoutubeUrl(url: string)   { return /(?:youtube\.com\/watch\?.*v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]{11}/.test(url); }

export default function AddPage() {
  const router = useRouter();

  // ── Source form state ──────────────────────────────────────────────────────
  const [source, setSource] = useState<SourceKind>("pdf");
  const [file,   setFile]   = useState<File | null>(null);
  const [text,   setText]   = useState("");
  const [url,    setUrl]    = useState("");
  const [backend, setBackend] = useState<string>("gemini");

  // ── Page view + shared async state ────────────────────────────────────────
  const [view,  setView]  = useState<PageView>("source");
  const [busy,  setBusy]  = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Picker state ──────────────────────────────────────────────────────────
  const [videoRecipes,    setVideoRecipes]    = useState<VideoRecipeItem[]>([]);
  const [pickerSelection, setPickerSelection] = useState<Set<number>>(new Set());

  // ── Sequential flow state ─────────────────────────────────────────────────
  const [flowQueue,        setFlowQueue]        = useState<VideoRecipeItem[]>([]);
  const [flowTotal,        setFlowTotal]        = useState(0);
  const [flowDone,         setFlowDone]         = useState(0);   // recipes saved so far
  const [flowCurrentTitle, setFlowCurrentTitle] = useState("");  // title being processed
  const [draft,            setDraft]            = useState<RecipeDraft | null>(null);

  // ── Image generation state ────────────────────────────────────────────────
  const [imageBlob,    setImageBlob]    = useState<Blob | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError,   setImageError]   = useState<string | null>(null);
  const [imageStyles,  setImageStyles]  = useState<{ id: string; label: string }[]>([]);
  const [selectedStyle, setSelectedStyle] = useState("ghibli");
  const [referenceBlob, setReferenceBlob] = useState<Blob | null>(null);

  useEffect(() => {
    api.getInfo().then((info) => setBackend(info.extractor_backend)).catch(() => {});
    api.getImageStyles().then(setImageStyles).catch(() => {});
  }, []);

  const videoBlocked = source === "video" && (isTwitterUrl(url) || isInstagramUrl(url)) && backend !== "gemini";

  // ── Helpers ────────────────────────────────────────────────────────────────

  function resetToSource() {
    setView("source");
    setVideoRecipes([]);
    setPickerSelection(new Set());
    setFlowQueue([]);
    setFlowTotal(0);
    setFlowDone(0);
    setFlowCurrentTitle("");
    setDraft(null);
    setImageBlob(null);
    setReferenceBlob(null);
    setError(null);
    setBusy(false);
  }

  async function fetchRecipeFromVideo(item: VideoRecipeItem) {
    setFlowCurrentTitle(item.title);
    const form = new FormData();
    form.set("source_type", "video");
    form.set("url", url);
    form.set("recipe_hint", item.title);
    const result = await api.extractDraft(form);
    setDraft(result);
  }

  // ── Phase 1: extract ───────────────────────────────────────────────────────

  async function extract() {
    setError(null);
    setBusy(true);
    try {
      if ((source === "url" || source === "video") && url.trim()) {
        const existing = await api.checkSource(url.trim());
        if (existing.duplicate) {
          throw new Error(`Esta fuente ya está guardada como «${existing.title}».`);
        }
      }
      if (source === "video" && isYoutubeUrl(url)) {
        if (!url.trim()) throw new Error("Introduce una URL");
        const listing = await api.listVideoRecipes(url);
        if (listing.recipes.length === 0) throw new Error("No se encontraron recetas en este vídeo");
        if (listing.recipes.length > 1) {
          setVideoRecipes(listing.recipes);
          setPickerSelection(new Set());
          setView("picker");
          return;
        }
        // Single recipe: skip picker, go straight to flow
        const only = listing.recipes[0];
        setFlowTotal(1);
        setFlowDone(0);
        setFlowQueue([]);
        setView("flow");
        await fetchRecipeFromVideo(only);
        return;
      }

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
      setFlowTotal(1);
      setFlowDone(0);
      setFlowQueue([]);
      setFlowCurrentTitle("");
      setView("flow");
      const result = await api.extractDraft(form);
      setDraft(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      setView("source");
    } finally {
      setBusy(false);
    }
  }

  // ── Picker: confirm selection ──────────────────────────────────────────────

  async function confirmSelection() {
    const selected = videoRecipes.filter((r) => pickerSelection.has(r.index));
    if (selected.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const [first, ...rest] = selected;
      setFlowTotal(selected.length);
      setFlowDone(0);
      setFlowQueue(rest);
      setView("flow");
      await fetchRecipeFromVideo(first);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      setView("picker");
    } finally {
      setBusy(false);
    }
  }

  function toggleSelection(index: number) {
    setPickerSelection((prev) => {
      const next = new Set(prev);
      next.has(index) ? next.delete(index) : next.add(index);
      return next;
    });
  }

  function toggleAll() {
    setPickerSelection((prev) =>
      prev.size === videoRecipes.length
        ? new Set()
        : new Set(videoRecipes.map((r) => r.index))
    );
  }

  // ── Image generation ───────────────────────────────────────────────────────

  const generateImage = useCallback(async (style: string) => {
    if (!draft) return;
    setImageLoading(true);
    setImageError(null);
    try {
      const blob = await api.generateImage(draft.title, draft.subtitle, draft.description, style, referenceBlob);
      setImageBlob(blob);
    } catch (e: unknown) {
      if (e instanceof Error && "status" in e && (e as { status: number }).status === 429) {
        setImageError(e.message || "Límite de generación de imágenes alcanzado.");
      }
    } finally {
      setImageLoading(false);
    }
  }, [draft, referenceBlob]);

  // ── Save & advance queue ───────────────────────────────────────────────────

  async function commit() {
    if (!draft) return;
    setError(null);
    setBusy(true);
    try {
      const autoRef =
        source === "url" || source === "video"
          ? url
          : source === "text" ? null : file?.name ?? null;
      const created = await api.createRecipe({
        ...draft,
        source_type: source,
        source_ref: draft.source_ref ?? autoRef,
        raw_text: source === "text" ? text : null,
      });
      if (imageBlob) {
        try { await api.uploadImage(created.id, imageBlob); } catch {}
      }

      const newDone = flowDone + 1;
      setFlowDone(newDone);

      if (flowQueue.length > 0) {
        const [next, ...rest] = flowQueue;
        setFlowQueue(rest);
        setDraft(null);
        setImageBlob(null);
        setReferenceBlob(null);
        await fetchRecipeFromVideo(next);
      } else {
        // All done — back to source picker
        resetToSource();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setBusy(false);
    }
  }

  // ── Floating progress bar (shown during flow) ──────────────────────────────

  const ProgressBar = view === "flow" ? (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-border shadow-lg">
      <div
        className="h-1 bg-accent transition-all duration-500"
        style={{ width: `${(flowDone / flowTotal) * 100}%` }}
      />
      <div className="flex items-center justify-between px-6 py-3 max-w-3xl mx-auto">
        <span className="text-sm text-muted truncate">
          {draft === null
            ? <>Cargando <span className="font-medium text-foreground">"{flowCurrentTitle}"</span>…</>
            : <><span className="font-medium text-foreground">"{flowCurrentTitle}"</span></>
          }
        </span>
        <span className="text-sm font-medium text-muted ml-4 flex-none">
          {flowDone + 1} / {flowTotal}
        </span>
      </div>
    </div>
  ) : null;

  // ── Render: flow ───────────────────────────────────────────────────────────

  if (view === "flow") {
    if (draft === null) {
      return (
        <>
          <div className="flex flex-col items-center gap-4 py-24 max-w-3xl">
            <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
            <p className="text-sm text-muted">Extrayendo "{flowCurrentTitle}"…</p>
          </div>
          {ProgressBar}
        </>
      );
    }
    return (
      <>
        <div className="pb-16">
          <RecipeForm
            draft={draft}
            setDraft={setDraft}
            header="Revisa antes de guardar"
            onBack={resetToSource}
            backLabel="✕ Cancelar"
            onSubmit={commit}
            busy={busy}
            error={error}
            imageBlob={imageBlob}
            imageLoading={imageLoading}
            imageError={imageError}
            onDismissImageError={() => setImageError(null)}
            imageStyles={imageStyles}
            selectedStyle={selectedStyle}
            onStyleSelect={(s) => setSelectedStyle(s)}
            onGenerateImage={(s) => generateImage(s)}
            referenceImage={referenceBlob}
            onReferenceImageChange={setReferenceBlob}
          />
        </div>
        {ProgressBar}
      </>
    );
  }

  // ── Render: picker ─────────────────────────────────────────────────────────

  if (view === "picker") {
    const allSelected = pickerSelection.size === videoRecipes.length;
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Elige recetas</h1>
          <p className="text-sm text-muted">
            Este vídeo contiene {videoRecipes.length} recetas. Selecciona las que quieres guardar.
          </p>
        </header>

        <div className="flex flex-col gap-3">
          {videoRecipes.map((item) => {
            const selected = pickerSelection.has(item.index);
            return (
              <button
                key={item.index}
                type="button"
                onClick={() => toggleSelection(item.index)}
                disabled={busy}
                className={`flex items-start gap-3 p-4 rounded-xl border text-left transition disabled:opacity-60 ${
                  selected
                    ? "border-accent bg-accent-soft"
                    : "border-border bg-card hover:border-accent/40"
                }`}
              >
                <span className={`mt-0.5 flex-none w-4 h-4 rounded border flex items-center justify-center text-xs font-bold ${
                  selected ? "bg-accent border-accent text-white" : "border-border"
                }`}>
                  {selected ? "✓" : ""}
                </span>
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium text-sm">{item.title}</span>
                  <span className="text-xs text-muted">{item.description}</span>
                </span>
              </button>
            );
          })}
        </div>

        {error && (
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">{error}</p>
        )}

        <div className="flex items-center justify-between gap-3">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setView("source")}
              className="px-4 py-2 rounded-md border border-border text-sm hover:bg-zinc-50"
            >
              ← Cambiar vídeo
            </button>
            <button
              type="button"
              onClick={toggleAll}
              className="px-4 py-2 rounded-md border border-border text-sm hover:bg-zinc-50"
            >
              {allSelected ? "Deseleccionar todo" : "Seleccionar todo"}
            </button>
          </div>
          <button
            type="button"
            onClick={confirmSelection}
            disabled={busy || pickerSelection.size === 0}
            className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
          >
            {busy
              ? "Extrayendo…"
              : pickerSelection.size <= 1
                ? "Extraer →"
                : `Extraer ${pickerSelection.size} →`}
          </button>
        </div>
      </div>
    );
  }

  // ── Render: source picker ──────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Nueva receta</h1>
        <p className="text-sm text-muted">
          Elige el origen, la IA extraerá los ingredientes y los pasos, y revisas antes de guardar.
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
            {file && <span className="text-xs text-muted">{file.name} · {(file.size / 1024).toFixed(0)} KB</span>}
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
              placeholder="Pega aquí la receta en texto plano…"
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
              placeholder="https://…"
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
              placeholder="https://youtube.com/watch?v=… · instagram.com/reel/… · x.com/…/status/…"
              className="border border-border rounded-md p-2 text-sm focus:border-accent outline-none"
            />
            <span className="text-xs text-muted">YouTube (subtítulos), Instagram (vídeo) y Twitter/X (vídeo)</span>
            {videoBlocked && (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
                Los vídeos de Twitter/X e Instagram requieren el backend Gemini. El backend actual (Claude) no admite procesamiento de vídeo directo.
              </p>
            )}
          </label>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">{error}</p>
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
          disabled={busy || videoBlocked}
          className="px-5 py-2 rounded-md bg-accent text-white text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Extrayendo…" : "Extraer →"}
        </button>
      </div>
    </div>
  );
}
