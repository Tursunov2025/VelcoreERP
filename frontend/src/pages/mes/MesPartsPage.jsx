import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const emptyForm = {
  part_number: "",
  name: "",
  unit: "dona",
  description: "",
};

export default function MesPartsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("mes_view");
  const canEdit = isAdmin || hasPermission("mes_edit");
  const canDelete = isAdmin || hasPermission("mes_delete");

  const [parts, setParts] = useState([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.mesGetParts({ q: debouncedSearch });
      setParts(data.parts || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, debouncedSearch]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const resetForm = () => {
    setForm(emptyForm);
    setEditId(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.part_number.trim() || !form.name.trim()) return;
    const body = {
      part_number: form.part_number.trim(),
      name: form.name.trim(),
      unit: form.unit.trim() || "dona",
      description: form.description,
    };
    try {
      if (editId) {
        await api.mesUpdatePart(editId, body);
        setToast(t("common.saved"));
      } else {
        await api.mesCreatePart(body);
        setToast(t("mes.addPart"));
      }
      resetForm();
      load();
    } catch (err) {
      setToast(err.message);
    }
  };

  const startEdit = (part) => {
    setEditId(part.id);
    setForm({
      part_number: part.part_number,
      name: part.name,
      unit: part.unit || "dona",
      description: part.description || "",
    });
  };

  const remove = async (part) => {
    if (!window.confirm(`${part.part_number} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeletePart(part.id);
      setToast(t("mes.delete"));
      load();
    } catch (err) {
      setToast(err.message);
    }
  };

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div>
      <div className="mb-4">
        <Link to="/mes" className="text-sm text-[var(--brand-primary)] hover:underline">
          ← {t("mes.backHub")}
        </Link>
      </div>
      <PageHeader title={t("mes.partsTitle")} subtitle={t("mes.partsSubtitle")} />

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={t("mes.searchParts")}
        className="mb-4 w-full rounded-xl border px-4 py-3"
      />

      {canEdit && (
        <form
          onSubmit={submit}
          className="mb-6 grid gap-3 rounded-2xl border bg-[var(--brand-card)] p-4 md:grid-cols-2"
        >
          <input
            value={form.part_number}
            onChange={(e) => setForm({ ...form, part_number: e.target.value })}
            placeholder={t("mes.partNumber")}
            className="rounded-xl border px-4 py-2 font-mono uppercase"
            required
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t("mes.name")}
            className="rounded-xl border px-4 py-2"
            required
          />
          <input
            value={form.unit}
            onChange={(e) => setForm({ ...form, unit: e.target.value })}
            placeholder={t("mes.unit")}
            className="rounded-xl border px-4 py-2"
          />
          <input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder={t("mes.description")}
            className="rounded-xl border px-4 py-2"
          />
          <div className="flex gap-2 md:col-span-2">
            <button
              type="submit"
              className="brand-btn rounded-xl px-4 py-2 font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {editId ? t("mes.editPart") : t("mes.addPart")}
            </button>
            {editId && (
              <button type="button" onClick={resetForm} className="rounded-xl border px-4 py-2">
                {t("common.cancel")}
              </button>
            )}
          </div>
        </form>
      )}

      {error && <ErrorAlert message={error} />}
      {loading ? (
        <LoadingSpinner />
      ) : parts.length === 0 ? (
        <p className="text-center text-[var(--brand-muted)]">{t("mes.emptyParts")}</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-[var(--brand-card)]">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left">
                <th className="px-4 py-3">{t("mes.partNumber")}</th>
                <th className="px-4 py-3">{t("mes.name")}</th>
                <th className="px-4 py-3">{t("mes.unit")}</th>
                <th className="px-4 py-3">{t("mes.description")}</th>
                {canEdit && <th className="px-4 py-3" />}
              </tr>
            </thead>
            <tbody>
              {parts.map((part) => (
                <tr key={part.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-mono font-semibold">{part.part_number}</td>
                  <td className="px-4 py-3">{part.name}</td>
                  <td className="px-4 py-3">{part.unit}</td>
                  <td className="px-4 py-3 text-[var(--brand-muted)]">
                    {part.description || "—"}
                  </td>
                  {canEdit && (
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => startEdit(part)}
                        className="mr-2 text-[var(--brand-primary)]"
                      >
                        {t("common.edit")}
                      </button>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => remove(part)}
                          className="text-red-600"
                        >
                          {t("mes.delete")}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
