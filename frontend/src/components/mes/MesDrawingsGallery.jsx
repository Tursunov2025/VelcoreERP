import { useCallback, useEffect, useRef, useState } from "react";
import { api, API_BASE } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

function resolveUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

function isImage(contentType, url) {
  const ct = (contentType || "").toLowerCase();
  if (ct.startsWith("image/")) return true;
  return /\.(png|jpe?g|webp|gif|svg)$/i.test(url || "");
}

function formatSize(bytes) {
  const n = Number(bytes);
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MesDrawingsGallery({
  templateId,
  readOnly = false,
  onCountChange,
}) {
  const { t } = useLocale();
  const fileRef = useRef(null);
  const [drawings, setDrawings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadRevision, setUploadRevision] = useState("A");
  const [uploadPrimary, setUploadPrimary] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.mesGetTemplateDrawings(templateId);
      setDrawings(data.drawings || []);
      onCountChange?.(data.count ?? (data.drawings || []).length);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [templateId, onCountChange]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.mesUploadDrawing(templateId, file, {
        title: uploadTitle.trim() || file.name,
        revision: uploadRevision.trim() || "A",
        is_primary: uploadPrimary,
      });
      setUploadTitle("");
      setUploadRevision("A");
      setUploadPrimary(false);
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const setPrimary = async (drawing) => {
    try {
      await api.mesSetPrimaryDrawing(templateId, drawing.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (drawing) => {
    if (!window.confirm(`${drawing.title} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeleteDrawing(templateId, drawing.id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const updateMeta = async (drawing, patch) => {
    try {
      await api.mesUpdateDrawing(templateId, drawing.id, patch);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <p className="py-6 text-center text-sm text-[var(--brand-muted)]">{t("common.loading")}</p>
    );
  }

  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-bold">{t("mes.drawingsGallery")}</h3>
        <span className="text-sm text-[var(--brand-muted)]">
          {drawings.length} {t("mes.drawingCount").toLowerCase()}
        </span>
      </div>

      {readOnly && (
        <p className="mb-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("mes.drawingsReadOnly")}
        </p>
      )}

      {!readOnly && (
        <div className="mb-6 rounded-xl border bg-gray-50 p-4">
          <p className="mb-2 text-sm font-semibold">{t("mes.uploadDrawingFile")}</p>
          <div className="flex flex-wrap gap-2">
            <input
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
              placeholder={t("mes.drawingTitle")}
              className="min-w-[160px] flex-1 rounded-xl border px-3 py-2 text-sm"
            />
            <input
              value={uploadRevision}
              onChange={(e) => setUploadRevision(e.target.value.toUpperCase())}
              placeholder={t("mes.drawingRevision")}
              className="w-20 rounded-xl border px-3 py-2 text-sm font-mono uppercase"
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={uploadPrimary}
                onChange={(e) => setUploadPrimary(e.target.checked)}
              />
              {t("mes.setPrimaryDrawing")}
            </label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*,.pdf,.svg"
              className="hidden"
              onChange={upload}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {uploading ? t("common.saving") : t("mes.uploadDrawing")}
            </button>
          </div>
        </div>
      )}

      {drawings.length === 0 ? (
        <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.emptyDrawings")}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {drawings.map((drawing) => {
            const url = resolveUrl(drawing.url);
            const image = isImage(drawing.content_type, drawing.url);
            return (
              <div
                key={drawing.id}
                className={`overflow-hidden rounded-xl border ${
                  drawing.is_primary ? "ring-2 ring-[var(--brand-primary)]" : ""
                }`}
              >
                <button
                  type="button"
                  onClick={() => setPreview(drawing)}
                  className="flex aspect-[4/3] w-full items-center justify-center bg-gray-100"
                >
                  {image ? (
                    <img src={url} alt={drawing.title} className="h-full w-full object-contain" />
                  ) : (
                    <span className="text-4xl">📄</span>
                  )}
                </button>
                <div className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      {readOnly ? (
                        <p className="truncate font-semibold">{drawing.title}</p>
                      ) : (
                        <input
                          defaultValue={drawing.title}
                          onBlur={(e) => {
                            if (e.target.value.trim() && e.target.value !== drawing.title) {
                              updateMeta(drawing, { title: e.target.value.trim() });
                            }
                          }}
                          className="w-full truncate rounded border px-2 py-1 text-sm font-semibold"
                        />
                      )}
                      <p className="text-xs text-[var(--brand-muted)]">
                        Rev {drawing.revision} · {formatSize(drawing.file_size)}
                      </p>
                    </div>
                    {drawing.is_primary && (
                      <span className="shrink-0 rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
                        ★
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[var(--brand-primary)] hover:underline"
                    >
                      {t("mes.openDrawing")}
                    </a>
                    {!readOnly && !drawing.is_primary && (
                      <button
                        type="button"
                        onClick={() => setPrimary(drawing)}
                        className="text-xs text-[var(--brand-primary)]"
                      >
                        {t("mes.setPrimaryDrawing")}
                      </button>
                    )}
                    {!readOnly && (
                      <button
                        type="button"
                        onClick={() => remove(drawing)}
                        className="text-xs text-red-600"
                      >
                        {t("mes.delete")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreview(null)}
          onKeyDown={(e) => e.key === "Escape" && setPreview(null)}
          role="presentation"
        >
          <div
            className="max-h-[90vh] max-w-4xl overflow-auto rounded-xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="font-bold">
                {preview.title} · Rev {preview.revision}
              </p>
              <button type="button" onClick={() => setPreview(null)} className="text-sm">
                ✕
              </button>
            </div>
            {isImage(preview.content_type, preview.url) ? (
              <img
                src={resolveUrl(preview.url)}
                alt={preview.title}
                className="max-h-[70vh] w-full object-contain"
              />
            ) : (
              <iframe
                title={preview.title}
                src={resolveUrl(preview.url)}
                className="h-[70vh] w-full min-w-[300px] rounded border"
              />
            )}
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  );
}
