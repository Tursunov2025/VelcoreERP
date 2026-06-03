import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function MaterialPartBomPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [parts, setParts] = useState([]);
  const [selectedPartId, setSelectedPartId] = useState("");
  const [partInfo, setPartInfo] = useState(null);
  const [lines, setLines] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [materialId, setMaterialId] = useState("");
  const [qtyPerPart, setQtyPerPart] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const loadParts = useCallback(async () => {
    if (!canView) return;
    try {
      const data = await api.materialsPlanningParts();
      setParts(data.parts || []);
    } catch (e) {
      setError(e.message);
    }
  }, [canView]);

  const loadPartBom = useCallback(async () => {
    if (!selectedPartId || !canView) return;
    setError("");
    setBusy(true);
    try {
      const data = await api.materialsPartBom(Number(selectedPartId));
      setPartInfo(data.part);
      setLines(data.lines || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }, [selectedPartId, canView]);

  useEffect(() => {
    loadParts().finally(() => setLoading(false));
  }, [loadParts]);

  useEffect(() => {
    if (!canEdit) return;
    api.materialsItems().then((data) => setMaterials(data.materials || [])).catch(() => {});
  }, [canEdit]);

  useEffect(() => {
    if (selectedPartId) loadPartBom();
    else {
      setPartInfo(null);
      setLines([]);
    }
  }, [selectedPartId, loadPartBom]);

  const addLine = async () => {
    if (!canEdit || !selectedPartId || !materialId || !qtyPerPart) return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsAddPartBomLine(Number(selectedPartId), {
        material_id: Number(materialId),
        quantity_per_part: Number(qtyPerPart),
      });
      setMaterialId("");
      setQtyPerPart("");
      await loadPartBom();
      await loadParts();
      setToast(t("materials.partBomSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const updateQty = async (line, value) => {
    const qty = Number(value);
    if (!qty || qty <= 0 || qty === line.quantity_per_part) return;
    setBusy(true);
    try {
      await api.materialsUpdatePartBomLine(Number(selectedPartId), line.id, {
        quantity_per_part: qty,
      });
      await loadPartBom();
      setToast(t("materials.partBomSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeLine = async (line) => {
    if (!window.confirm(`${line.material_code} — ${t("mes.confirmDelete")}?`)) return;
    setBusy(true);
    try {
      await api.materialsDeletePartBomLine(Number(selectedPartId), line.id);
      await loadPartBom();
      await loadParts();
      setToast(t("materials.partBomSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const existingMaterialIds = new Set(lines.map((l) => l.material_id));

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.partBomTitle")} subtitle={t("materials.partBomSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={loadParts} />

      <select
        value={selectedPartId}
        onChange={(e) => setSelectedPartId(e.target.value)}
        className="mb-4 min-h-[48px] w-full rounded-xl border px-3 font-mono"
      >
        <option value="">{t("materials.selectPart")}</option>
        {parts.map((p) => (
          <option key={p.id} value={p.id}>
            {p.part_number} — {p.name} ({p.material_bom_count})
          </option>
        ))}
      </select>

      {partInfo ? (
        <div className="mb-4 rounded-xl border bg-[var(--brand-card)] p-4">
          <p className="font-mono font-bold text-[var(--brand-primary)]">{partInfo.part_number}</p>
          <p className="font-bold">{partInfo.name}</p>
          <p className="text-sm text-[var(--brand-muted)]">{partInfo.unit}</p>
        </div>
      ) : null}

      {canEdit && selectedPartId ? (
        <div className="mb-4 space-y-2 rounded-2xl border bg-gray-50 p-4">
          <p className="text-sm font-semibold">{t("materials.addMaterialToPart")}</p>
          <select
            value={materialId}
            onChange={(e) => setMaterialId(e.target.value)}
            className="min-h-[48px] w-full rounded-xl border px-3"
            disabled={busy}
          >
            <option value="">{t("materials.selectMaterial")}</option>
            {materials
              .filter((m) => !existingMaterialIds.has(m.id))
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.code} — {m.name} ({m.unit})
                </option>
              ))}
          </select>
          <input
            type="number"
            min="0.0001"
            step="any"
            value={qtyPerPart}
            onChange={(e) => setQtyPerPart(e.target.value)}
            placeholder={t("materials.qtyPerPart")}
            className="min-h-[48px] w-full rounded-xl border px-3"
            disabled={busy}
          />
          <button
            type="button"
            disabled={busy || !materialId || !qtyPerPart}
            onClick={addLine}
            className="min-h-[48px] w-full rounded-xl font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {t("common.add")}
          </button>
        </div>
      ) : null}

      <div className="space-y-2">
        {lines.map((line) => (
          <div key={line.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-mono text-sm font-bold">{line.material_code}</p>
                <p className="font-bold">{line.material_name}</p>
                <p className="text-sm text-[var(--brand-muted)]">{line.material_unit}</p>
              </div>
              {canEdit ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => removeLine(line)}
                  className="min-h-[44px] rounded-xl border border-red-200 px-3 text-sm font-bold text-red-600"
                >
                  {t("common.delete")}
                </button>
              ) : null}
            </div>
            <div className="mt-2">
              <label className="text-xs text-[var(--brand-muted)]">{t("materials.qtyPerPart")}</label>
              {canEdit ? (
                <input
                  type="number"
                  min="0.0001"
                  step="any"
                  defaultValue={line.quantity_per_part}
                  disabled={busy}
                  onBlur={(e) => updateQty(line, e.target.value)}
                  className="mt-1 min-h-[44px] w-full rounded-xl border px-3 font-bold"
                />
              ) : (
                <p className="font-bold">{formatQty(line.quantity_per_part)}</p>
              )}
            </div>
          </div>
        ))}
        {selectedPartId && !busy && lines.length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("materials.partBomEmpty")}</p>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
