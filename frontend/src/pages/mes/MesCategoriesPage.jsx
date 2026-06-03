import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const emptyForm = { name: "", description: "", parent_id: "", sort_order: 0 };

export default function MesCategoriesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("mes_view");
  const canEdit = isAdmin || hasPermission("mes_edit");
  const canDelete = isAdmin || hasPermission("mes_delete");

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.mesGetCategories();
      setCategories(data.categories || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

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
    if (!form.name.trim()) return;
    const body = {
      name: form.name.trim(),
      description: form.description,
      parent_id: form.parent_id ? Number(form.parent_id) : null,
      sort_order: Number(form.sort_order) || 0,
    };
    try {
      if (editId) {
        await api.mesUpdateCategory(editId, body);
        setToast(t("common.saved"));
      } else {
        await api.mesCreateCategory(body);
        setToast(t("mes.addCategory"));
      }
      resetForm();
      load();
    } catch (err) {
      setToast(err.message);
    }
  };

  const startEdit = (cat) => {
    setEditId(cat.id);
    setForm({
      name: cat.name,
      description: cat.description || "",
      parent_id: cat.parent_id ?? "",
      sort_order: cat.sort_order ?? 0,
    });
  };

  const remove = async (cat) => {
    if (!window.confirm(`${cat.name} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeleteCategory(cat.id);
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
      <PageHeader title={t("mes.categoriesTitle")} subtitle={t("mes.categoriesSubtitle")} />

      {canEdit && (
        <form
          onSubmit={submit}
          className="mb-6 grid gap-3 rounded-2xl border bg-[var(--brand-card)] p-4 md:grid-cols-2"
        >
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t("mes.name")}
            className="rounded-xl border px-4 py-2"
            required
          />
          <input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder={t("mes.description")}
            className="rounded-xl border px-4 py-2"
          />
          <select
            value={form.parent_id}
            onChange={(e) => setForm({ ...form, parent_id: e.target.value })}
            className="rounded-xl border px-4 py-2"
          >
            <option value="">{t("mes.noParent")}</option>
            {categories
              .filter((c) => c.id !== editId)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
          <input
            type="number"
            value={form.sort_order}
            onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
            placeholder={t("mes.sortOrder")}
            className="rounded-xl border px-4 py-2"
          />
          <div className="flex gap-2 md:col-span-2">
            <button
              type="submit"
              className="brand-btn rounded-xl px-4 py-2 font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {editId ? t("mes.editCategory") : t("mes.addCategory")}
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
      ) : categories.length === 0 ? (
        <p className="text-center text-[var(--brand-muted)]">{t("mes.emptyCategories")}</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-[var(--brand-card)]">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left">
                <th className="px-4 py-3">{t("mes.name")}</th>
                <th className="px-4 py-3">{t("mes.parent")}</th>
                <th className="px-4 py-3">{t("mes.templates")}</th>
                <th className="px-4 py-3">{t("mes.sortOrder")}</th>
                {canEdit && <th className="px-4 py-3" />}
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => {
                const parent = categories.find((c) => c.id === cat.parent_id);
                return (
                  <tr key={cat.id} className="border-b last:border-0">
                    <td className="px-4 py-3 font-semibold">{cat.name}</td>
                    <td className="px-4 py-3">{parent?.name || "—"}</td>
                    <td className="px-4 py-3">{cat.template_count ?? 0}</td>
                    <td className="px-4 py-3">{cat.sort_order}</td>
                    {canEdit && (
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => startEdit(cat)}
                          className="mr-2 text-[var(--brand-primary)]"
                        >
                          {t("common.edit")}
                        </button>
                        {canDelete && (
                          <button
                            type="button"
                            onClick={() => remove(cat)}
                            className="text-red-600"
                          >
                            {t("mes.delete")}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
