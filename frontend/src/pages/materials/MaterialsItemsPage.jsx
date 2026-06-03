import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const EMPTY_FORM = {
  code: "",
  name: "",
  unit: "dona",
  category_id: "",
  minimum_stock: "0",
  current_stock: "0",
  unit_cost: "0",
};

export default function MaterialsItemsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [materials, setMaterials] = useState([]);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editId, setEditId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const [itemsRes, catRes] = await Promise.all([
        api.materialsItems(true),
        api.materialsCategories(),
      ]);
      setMaterials(itemsRes.materials || []);
      setCategories(catRes.categories || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (mat) => {
    setEditId(mat.id);
    setForm({
      code: mat.code || "",
      name: mat.name || "",
      unit: mat.unit || "dona",
      category_id: mat.category_id ? String(mat.category_id) : "",
      minimum_stock: String(mat.minimum_stock ?? 0),
      current_stock: String(mat.current_stock ?? 0),
      unit_cost: String(mat.unit_cost ?? 0),
    });
    setShowForm(true);
  };

  const save = async () => {
    if (!canEdit) return;
    setBusy(true);
    setToast("");
    try {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        unit: form.unit.trim() || "dona",
        category_id: form.category_id ? Number(form.category_id) : null,
        minimum_stock: Number(form.minimum_stock) || 0,
        unit_cost: Number(form.unit_cost) || 0,
      };
      if (editId) {
        await api.materialsUpdateItem(editId, payload);
      } else {
        await api.materialsCreateItem({
          ...payload,
          current_stock: Number(form.current_stock) || 0,
        });
      }
      setShowForm(false);
      await load();
      setToast(t("materials.itemSaved"));
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

      <PageHeader title={t("materials.itemsTitle")} subtitle={t("materials.itemsSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {canEdit ? (
        <button
          type="button"
          onClick={openCreate}
          className="mb-4 min-h-[48px] w-full rounded-xl font-bold text-white sm:w-auto sm:px-8"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          + {t("materials.addItem")}
        </button>
      ) : null}

      {showForm && canEdit ? (
        <div className="mb-4 space-y-2 rounded-2xl border bg-[var(--brand-card)] p-4">
          <input
            type="text"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
            placeholder={t("materials.fieldCode")}
            className="min-h-[48px] w-full rounded-xl border px-3 font-mono"
            disabled={busy}
          />
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t("materials.fieldName")}
            className="min-h-[48px] w-full rounded-xl border px-3"
            disabled={busy}
          />
          <div className="grid gap-2 sm:grid-cols-2">
            <input
              type="text"
              value={form.unit}
              onChange={(e) => setForm({ ...form, unit: e.target.value })}
              placeholder={t("materials.fieldUnit")}
              className="min-h-[48px] rounded-xl border px-3"
              disabled={busy}
            />
            <select
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              className="min-h-[48px] rounded-xl border px-3"
              disabled={busy}
            >
              <option value="">{t("materials.noCategory")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <input
              type="number"
              min="0"
              step="any"
              value={form.minimum_stock}
              onChange={(e) => setForm({ ...form, minimum_stock: e.target.value })}
              placeholder={t("materials.fieldMinStock")}
              className="min-h-[48px] rounded-xl border px-3"
              disabled={busy}
            />
            {!editId ? (
              <input
                type="number"
                min="0"
                step="any"
                value={form.current_stock}
                onChange={(e) => setForm({ ...form, current_stock: e.target.value })}
                placeholder={t("materials.fieldCurrentStock")}
                className="min-h-[48px] rounded-xl border px-3"
                disabled={busy}
              />
            ) : null}
            <input
              type="number"
              min="0"
              step="any"
              value={form.unit_cost}
              onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
              placeholder={t("materials.fieldUnitCost")}
              className="min-h-[48px] rounded-xl border px-3"
              disabled={busy}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={save}
              className="min-h-[48px] flex-1 rounded-xl font-bold text-white disabled:opacity-60"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {t("common.save")}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setShowForm(false)}
              className="min-h-[48px] rounded-xl border px-6 font-bold"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        {materials.map((mat) => (
          <div
            key={mat.id}
            className={`rounded-xl border p-4 ${mat.low_stock ? "border-red-300 bg-red-50/50" : "bg-[var(--brand-card)]"}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-mono text-sm font-bold text-[var(--brand-primary)]">{mat.code}</p>
                <p className="font-bold">{mat.name}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {mat.category_name || t("materials.noCategory")} · {mat.unit}
                </p>
              </div>
              {canEdit ? (
                <button
                  type="button"
                  onClick={() => openEdit(mat)}
                  className="min-h-[44px] shrink-0 rounded-xl border px-4 text-sm font-bold"
                >
                  {t("common.edit")}
                </button>
              ) : null}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldCurrentStock")}: </span>
                <strong className={mat.low_stock ? "text-red-600" : ""}>{mat.current_stock}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldMinStock")}: </span>
                <strong>{mat.minimum_stock}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldUnitCost")}: </span>
                <strong>{mat.unit_cost?.toLocaleString()}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.inventoryValue")}: </span>
                <strong>{mat.inventory_value?.toLocaleString()}</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
