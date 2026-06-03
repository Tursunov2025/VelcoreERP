import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

export default function MaterialsAdjustmentsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [materials, setMaterials] = useState([]);
  const [adjustments, setAdjustments] = useState([]);
  const [materialId, setMaterialId] = useState("");
  const [quantityAfter, setQuantityAfter] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const selected = materials.find((m) => String(m.id) === materialId);

  const load = useCallback(async () => {
    if (!canEdit) return;
    setError("");
    try {
      const [itemsRes, adjRes] = await Promise.all([
        api.materialsItems(),
        api.materialsAdjustments(),
      ]);
      setMaterials(itemsRes.materials || []);
      setAdjustments(adjRes.adjustments || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    if (!materialId || quantityAfter === "") return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsCreateAdjustment({
        material_id: Number(materialId),
        quantity_after: Number(quantityAfter),
        reason: reason.trim(),
        notes: notes.trim(),
      });
      setQuantityAfter("");
      setReason("");
      setNotes("");
      await load();
      setToast(t("materials.adjustmentSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!canEdit) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.adjustmentsTitle")} subtitle={t("materials.adjustmentsSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 space-y-2 rounded-2xl border bg-[var(--brand-card)] p-4">
        <select
          value={materialId}
          onChange={(e) => {
            setMaterialId(e.target.value);
            const mat = materials.find((m) => String(m.id) === e.target.value);
            if (mat) setQuantityAfter(String(mat.current_stock));
          }}
          className="min-h-[48px] w-full rounded-xl border px-3"
          disabled={busy}
        >
          <option value="">{t("materials.selectMaterial")}</option>
          {materials.map((m) => (
            <option key={m.id} value={m.id}>
              {m.code} — {m.name} ({m.current_stock} {m.unit})
            </option>
          ))}
        </select>
        {selected ? (
          <p className="text-sm text-[var(--brand-muted)]">
            {t("materials.currentStockLabel")}: <strong>{selected.current_stock}</strong> {selected.unit}
          </p>
        ) : null}
        <input
          type="number"
          min="0"
          step="any"
          value={quantityAfter}
          onChange={(e) => setQuantityAfter(e.target.value)}
          placeholder={t("materials.fieldQuantityAfter")}
          className="min-h-[48px] w-full rounded-xl border px-3"
          disabled={busy}
        />
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t("materials.fieldReason")}
          className="min-h-[48px] w-full rounded-xl border px-3"
          disabled={busy}
        />
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t("common.notes")}
          rows={2}
          className="w-full rounded-xl border px-3 py-2"
          disabled={busy}
        />
        <button
          type="button"
          disabled={busy || !materialId || quantityAfter === ""}
          onClick={submit}
          className="min-h-[48px] w-full rounded-xl font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("materials.submitAdjustment")}
        </button>
      </div>

      <h3 className="mb-2 font-bold">{t("materials.recentAdjustments")}</h3>
      <div className="space-y-2">
        {adjustments.map((a) => (
          <div key={a.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <p className="font-bold">
              {a.material_code} — {a.material_name}
            </p>
            <p className="text-sm">
              {a.quantity_before} → {a.quantity_after} ({a.adjustment_delta > 0 ? "+" : ""}
              {a.adjustment_delta}) · {formatDate(a.created_at)}
            </p>
            {a.reason ? <p className="text-xs text-[var(--brand-muted)]">{a.reason}</p> : null}
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
