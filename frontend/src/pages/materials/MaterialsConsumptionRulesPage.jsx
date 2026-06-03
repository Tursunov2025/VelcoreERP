import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const STAGES = ["Lazer", "Kraska"];

export default function MaterialsConsumptionRulesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [rules, setRules] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [materialId, setMaterialId] = useState("");
  const [stage, setStage] = useState("Lazer");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const [rulesRes, itemsRes] = await Promise.all([
        api.materialsConsumptionRules(true),
        canEdit ? api.materialsItems() : Promise.resolve({ materials: [] }),
      ]);
      setRules(rulesRes.rules || []);
      setMaterials(itemsRes.materials || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, canEdit]);

  useEffect(() => {
    load();
  }, [load]);

  const addRule = async () => {
    if (!canEdit || !materialId) return;
    setBusy(true);
    setToast("");
    try {
      await api.materialsCreateConsumptionRule({
        material_id: Number(materialId),
        consuming_stage: stage,
      });
      setMaterialId("");
      await load();
      setToast(t("materials.consumptionRuleSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleRule = async (rule) => {
    if (!canEdit) return;
    setBusy(true);
    try {
      await api.materialsUpdateConsumptionRule(rule.id, { is_active: !rule.is_active });
      await load();
      setToast(t("materials.consumptionRuleSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const existingKeys = new Set(rules.filter((r) => r.is_active).map((r) => `${r.material_id}-${r.consuming_stage}`));

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.consumptionRulesTitle")} subtitle={t("materials.consumptionRulesSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {canEdit ? (
        <div className="mb-4 space-y-2 rounded-2xl border bg-gray-50 p-4">
          <select
            value={materialId}
            onChange={(e) => setMaterialId(e.target.value)}
            className="min-h-[48px] w-full rounded-xl border px-3"
            disabled={busy}
          >
            <option value="">{t("materials.selectMaterial")}</option>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>
                {m.code} — {m.name}
              </option>
            ))}
          </select>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            className="min-h-[48px] w-full rounded-xl border px-3"
            disabled={busy}
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={busy || !materialId || existingKeys.has(`${materialId}-${stage}`)}
            onClick={addRule}
            className="min-h-[48px] w-full rounded-xl font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {t("common.add")}
          </button>
        </div>
      ) : null}

      <div className="space-y-2">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className={`flex items-center justify-between rounded-xl border p-4 ${
              rule.is_active ? "bg-[var(--brand-card)]" : "opacity-60"
            }`}
          >
            <div>
              <p className="font-mono text-sm font-bold">{rule.material_code}</p>
              <p className="font-bold">{rule.material_name}</p>
              <p className="text-sm text-[var(--brand-muted)]">
                {t("materials.consumingStage")}: <strong>{rule.consuming_stage}</strong>
              </p>
            </div>
            {canEdit ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => toggleRule(rule)}
                className="min-h-[44px] rounded-xl border px-4 text-sm font-bold"
              >
                {rule.is_active ? t("materials.deactivate") : t("materials.activate")}
              </button>
            ) : null}
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
