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

export default function MaterialsIssuesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [materials, setMaterials] = useState([]);
  const [issues, setIssues] = useState([]);
  const [materialId, setMaterialId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
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
      const [itemsRes, issuesRes] = await Promise.all([
        api.materialsItems(),
        api.materialsIssues(),
      ]);
      setMaterials(itemsRes.materials || []);
      setIssues(issuesRes.issues || []);
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
      await api.materialsCreateIssue({
        material_id: Number(materialId),
        quantity: Number(quantity),
        reason: reason.trim(),
        reference: reference.trim(),
        notes: notes.trim(),
      });
      setQuantity("");
      setReason("");
      setReference("");
      setNotes("");
      await load();
      setToast(t("materials.issueSaved"));
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

      <PageHeader title={t("materials.issuesTitle")} subtitle={t("materials.issuesSubtitle")} />

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
        <input
          type="number"
          min="0"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder={t("materials.fieldQuantity")}
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
          {t("materials.submitIssue")}
        </button>
      </div>

      <h3 className="mb-2 font-bold">{t("materials.recentIssues")}</h3>
      <div className="space-y-2">
        {issues.map((item) => (
          <div key={item.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <p className="font-bold">
              {item.material_code} — {item.material_name}
            </p>
            <p className="text-sm">
              -{item.quantity} · {formatDate(item.created_at)}
            </p>
            {item.reason ? <p className="text-xs text-[var(--brand-muted)]">{item.reason}</p> : null}
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
