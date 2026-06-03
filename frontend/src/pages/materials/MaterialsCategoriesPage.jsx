import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function MaterialsCategoriesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [categories, setCategories] = useState([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.materialsCategories(true);
      setCategories(data.categories || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  const addCategory = async () => {
    if (!canEdit || !name.trim()) return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsCreateCategory({ name: name.trim(), code: code.trim() });
      setName("");
      setCode("");
      await load();
      setToast(t("materials.categorySaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (cat) => {
    if (!canEdit) return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsUpdateCategory(cat.id, { is_active: !cat.is_active });
      await load();
      setToast(t("materials.categorySaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.categoriesTitle")} subtitle={t("materials.categoriesSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {canEdit ? (
        <div className="mb-4 grid gap-2 sm:grid-cols-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("materials.categoryName")}
            className="min-h-[48px] rounded-xl border px-3"
            disabled={busy}
          />
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder={t("materials.categoryCode")}
            className="min-h-[48px] rounded-xl border px-3 font-mono"
            disabled={busy}
          />
          <button
            type="button"
            disabled={busy || !name.trim()}
            onClick={addCategory}
            className="min-h-[48px] rounded-xl font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {t("common.add")}
          </button>
        </div>
      ) : null}

      <div className="space-y-2">
        {categories.map((cat) => (
          <div
            key={cat.id}
            className={`flex items-center justify-between rounded-xl border p-4 ${
              cat.is_active ? "bg-[var(--brand-card)]" : "opacity-60"
            }`}
          >
            <div>
              <p className="font-bold">{cat.name}</p>
              {cat.code ? <p className="font-mono text-sm text-[var(--brand-muted)]">{cat.code}</p> : null}
            </div>
            {canEdit ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => toggleActive(cat)}
                className="min-h-[44px] rounded-xl border px-4 text-sm font-bold"
              >
                {cat.is_active ? t("materials.deactivate") : t("materials.activate")}
              </button>
            ) : null}
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
