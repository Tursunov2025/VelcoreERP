import { useCallback, useEffect, useState } from "react";
import { api, API_BASE, getStoredTokens } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";
import { useLocale } from "../context/LocaleContext";

const FILE_ICONS = {
  pdf: "📕",
  docx: "📘",
  xlsx: "📗",
  xls: "📗",
  jpg: "🖼️",
  jpeg: "🖼️",
  png: "🖼️",
};

function fileIcon(name) {
  const ext = (name || "").split(".").pop()?.toLowerCase();
  return FILE_ICONS[ext] || "📄";
}

function formatSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function LlpPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("llp_view");
  const canUpload = isAdmin || hasPermission("llp_upload");
  const canEdit = isAdmin || hasPermission("llp_edit");
  const canDelete = isAdmin || hasPermission("llp_delete");
  const canDownload = isAdmin || hasPermission("llp_download");
  const canMarkRead = isAdmin || hasPermission("llp_read_confirm");

  const [folders, setFolders] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [folderName, setFolderName] = useState("");
  const [showFolderForm, setShowFolderForm] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    title: "",
    description: "",
    is_important: false,
    file: null,
  });
  const [editDoc, setEditDoc] = useState(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const [f, d] = await Promise.all([
        api.llpGetFolders(),
        api.llpGetDocuments({
          folder_id: selectedFolder ?? "",
          q: debouncedSearch,
        }),
      ]);
      setFolders(f.folders || []);
      setDocuments(d.documents || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, selectedFolder, debouncedSearch]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const createFolder = async (e) => {
    e.preventDefault();
    if (!folderName.trim()) return;
    try {
      await api.llpCreateFolder({
        name: folderName.trim(),
        parent_id: selectedFolder,
      });
      setFolderName("");
      setShowFolderForm(false);
      setToast(t("llp.folderCreated"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const uploadDocument = async (e) => {
    e.preventDefault();
    if (!uploadForm.file) {
      setToast(t("llp.selectFile"));
      return;
    }
    try {
      await api.llpUploadDocument(uploadForm.file, {
        title: uploadForm.title,
        description: uploadForm.description,
        folder_id: selectedFolder,
        is_important: uploadForm.is_important,
      });
      setUploadForm({ title: "", description: "", is_important: false, file: null });
      setToast(t("llp.uploaded"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const saveEdit = async () => {
    if (!editDoc) return;
    try {
      await api.llpUpdateDocument(editDoc.id, {
        title: editDoc.title,
        description: editDoc.description,
        folder_id: editDoc.folder_id,
        is_important: editDoc.is_important,
      });
      setEditDoc(null);
      setToast(t("notifications.saved"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const removeDoc = async (doc) => {
    if (!window.confirm(`"${doc.title}" ${t("llp.confirmDelete")}?`)) return;
    try {
      await api.llpDeleteDocument(doc.id);
      setToast(t("llp.deleted"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const markRead = async (doc) => {
    try {
      await api.llpMarkRead(doc.id);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const downloadDoc = async (doc) => {
    if (!canDownload) return;
    const tokens = getStoredTokens();
    const url = `${API_BASE}/llp/documents/${doc.id}/download`;
    const res = await fetch(url, {
      headers: tokens?.access_token
        ? { Authorization: `Bearer ${tokens.access_token}` }
        : {},
    });
    if (!res.ok) {
      setToast(t("notifications.error"));
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = doc.original_filename || doc.title;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (!canView) {
    return (
      <p className="py-12 text-center text-red-500">{t("llp.noAccess")}</p>
    );
  }

  return (
    <div>
      <BackButton fallback="/" label="Dashboard" className="mb-4" />
      <PageHeader title={t("llp.title")} subtitle={t("llp.subtitle")} />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("llp.searchPlaceholder")}
          className="flex-1 rounded-xl border px-4 py-3"
        />
        {canUpload && (
          <button
            type="button"
            onClick={() => setShowFolderForm((v) => !v)}
            className="brand-btn px-4 py-3 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            + {t("llp.newFolder")}
          </button>
        )}
      </div>

      {showFolderForm && canUpload && (
        <form
          onSubmit={createFolder}
          className="mb-4 flex flex-wrap gap-2 rounded-2xl border bg-[var(--brand-card)] p-4"
        >
          <input
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            placeholder={t("llp.folderName")}
            className="min-w-[200px] flex-1 rounded-xl border px-4 py-2"
          />
          <button type="submit" className="brand-btn px-4 py-2 text-white" style={{ backgroundColor: "var(--brand-button)" }}>
            {t("common.save")}
          </button>
        </form>
      )}

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <p className="mb-3 text-xs font-bold uppercase text-[var(--brand-muted)]">
            {t("llp.folders")}
          </p>
          <button
            type="button"
            onClick={() => setSelectedFolder(null)}
            className={`mb-1 w-full rounded-xl px-3 py-2 text-left text-sm ${
              selectedFolder === null ? "bg-black text-white" : "hover:bg-gray-100"
            }`}
          >
            {t("llp.allDocuments")}
          </button>
          {folders.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setSelectedFolder(f.id)}
              className={`mb-1 w-full rounded-xl px-3 py-2 text-left text-sm ${
                selectedFolder === f.id ? "bg-black text-white" : "hover:bg-gray-100"
              }`}
            >
              📁 {f.name} ({f.document_count})
            </button>
          ))}
        </aside>

        <div className="space-y-4">
          {canUpload && (
            <form
              onSubmit={uploadDocument}
              className="rounded-2xl border bg-[var(--brand-card)] p-4"
            >
              <h3 className="mb-3 font-bold">{t("llp.uploadDocument")}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  value={uploadForm.title}
                  onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                  placeholder={t("llp.docTitle")}
                  className="rounded-xl border px-4 py-2"
                />
                <input
                  type="file"
                  accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png"
                  onChange={(e) =>
                    setUploadForm({ ...uploadForm, file: e.target.files?.[0] || null })
                  }
                  className="text-sm"
                />
              </div>
              <textarea
                value={uploadForm.description}
                onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
                placeholder={t("llp.description")}
                className="mt-3 w-full rounded-xl border px-4 py-2"
                rows={2}
              />
              <label className="mt-3 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={uploadForm.is_important}
                  onChange={(e) =>
                    setUploadForm({ ...uploadForm, is_important: e.target.checked })
                  }
                />
                {t("llp.markImportant")}
              </label>
              <button
                type="submit"
                className="brand-btn mt-3 px-6 py-2 font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("llp.upload")}
              </button>
            </form>
          )}

          <ErrorAlert message={error} onRetry={load} />
          {loading ? (
            <LoadingSpinner />
          ) : documents.length === 0 ? (
            <p className="text-center text-[var(--brand-muted)]">{t("llp.empty")}</p>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className={`rounded-2xl border bg-[var(--brand-card)] p-4 ${
                    doc.is_important ? "border-amber-400 ring-1 ring-amber-200" : ""
                  } ${!doc.is_read ? "border-l-4 border-l-blue-500" : ""}`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-2 font-bold">
                        <span>{fileIcon(doc.original_filename)}</span>
                        {doc.title}
                        {doc.is_important && (
                          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                            {t("llp.important")}
                          </span>
                        )}
                        {!doc.is_read && (
                          <span className="rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                            {t("llp.unread")}
                          </span>
                        )}
                      </p>
                      <p className="mt-1 text-sm text-[var(--brand-muted)]">
                        {doc.original_filename} · {formatSize(doc.file_size)} · {doc.uploaded_by}
                      </p>
                      {doc.description && (
                        <p className="mt-2 text-sm">{doc.description}</p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {canDownload && (
                        <button
                          type="button"
                          onClick={() => downloadDoc(doc)}
                          className="rounded-xl border px-3 py-1 text-sm font-semibold"
                        >
                          {t("llp.download")}
                        </button>
                      )}
                      {canMarkRead && !doc.is_read && (
                        <button
                          type="button"
                          onClick={() => markRead(doc)}
                          className="rounded-xl bg-blue-600 px-3 py-1 text-sm font-semibold text-white"
                        >
                          {t("llp.markRead")}
                        </button>
                      )}
                      {canEdit && (
                        <button
                          type="button"
                          onClick={() => setEditDoc({ ...doc })}
                          className="rounded-xl border px-3 py-1 text-sm"
                        >
                          {t("common.edit")}
                        </button>
                      )}
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => removeDoc(doc)}
                          className="rounded-xl bg-red-500 px-3 py-1 text-sm text-white"
                        >
                          {t("common.delete")}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="brand-surface w-full max-w-md bg-[var(--brand-card)] p-6">
            <h3 className="mb-4 font-bold">{t("llp.editDocument")}</h3>
            <input
              value={editDoc.title}
              onChange={(e) => setEditDoc({ ...editDoc, title: e.target.value })}
              className="mb-3 w-full rounded-xl border px-4 py-2"
            />
            <textarea
              value={editDoc.description}
              onChange={(e) => setEditDoc({ ...editDoc, description: e.target.value })}
              className="mb-3 w-full rounded-xl border px-4 py-2"
              rows={3}
            />
            <select
              value={editDoc.folder_id ?? ""}
              onChange={(e) =>
                setEditDoc({
                  ...editDoc,
                  folder_id: e.target.value ? Number(e.target.value) : null,
                })
              }
              className="mb-3 w-full rounded-xl border px-4 py-2"
            >
              <option value="">{t("llp.noFolder")}</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
            <label className="mb-4 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editDoc.is_important}
                onChange={(e) => setEditDoc({ ...editDoc, is_important: e.target.checked })}
              />
              {t("llp.markImportant")}
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={saveEdit}
                className="brand-btn flex-1 py-2 font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("common.save")}
              </button>
              <button type="button" onClick={() => setEditDoc(null)} className="flex-1 rounded-xl border py-2">
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
