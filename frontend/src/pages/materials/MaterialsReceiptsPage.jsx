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

export default function MaterialsReceiptsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [materials, setMaterials] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [materialId, setMaterialId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canEdit) return;
    setError("");
    try {
      const [itemsRes, receiptsRes] = await Promise.all([
        api.materialsItems(),
        api.materialsReceipts(),
      ]);
      setMaterials(itemsRes.materials || []);
      setReceipts(receiptsRes.receipts || []);
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
    if (!materialId || !quantity) return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsCreateReceipt({
        material_id: Number(materialId),
        quantity: Number(quantity),
        unit_cost: unitCost ? Number(unitCost) : null,
        reference: reference.trim(),
        notes: notes.trim(),
      });
      setQuantity("");
      setUnitCost("");
      setReference("");
      setNotes("");
      await load();
      setToast(t("materials.receiptSaved"));
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

      <PageHeader title={t("materials.receiptsTitle")} subtitle={t("materials.receiptsSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 space-y-2 rounded-2xl border bg-[var(--brand-card)] p-4">
        <select
          value={materialId}
          onChange={(e) => setMaterialId(e.target.value)}
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
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            type="number"
            min="0"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder={t("materials.fieldQuantity")}
            className="min-h-[48px] rounded-xl border px-3"
            disabled={busy}
          />
          <input
            type="number"
            min="0"
            step="any"
            value={unitCost}
            onChange={(e) => setUnitCost(e.target.value)}
            placeholder={t("materials.fieldUnitCostOptional")}
            className="min-h-[48px] rounded-xl border px-3"
            disabled={busy}
          />
        </div>
        <input
          type="text"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder={t("materials.fieldReference")}
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
          disabled={busy || !materialId || !quantity}
          onClick={submit}
          className="min-h-[48px] w-full rounded-xl font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("materials.submitReceipt")}
        </button>
      </div>

      <h3 className="mb-2 font-bold">{t("materials.recentReceipts")}</h3>
      <div className="space-y-2">
        {receipts.map((r) => (
          <div key={r.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <p className="font-bold">
              {r.material_code} — {r.material_name}
            </p>
            <p className="text-sm">
              +{r.quantity} · {r.unit_cost?.toLocaleString()} · {formatDate(r.created_at)}
            </p>
            {r.reference ? <p className="text-xs text-[var(--brand-muted)]">{r.reference}</p> : null}
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
