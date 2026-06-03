import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function MaterialsConsumptionsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");

  const [consumptions, setConsumptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.materialsConsumptionsToday();
      setConsumptions(data.consumptions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  const totalCost = consumptions.reduce((sum, c) => sum + (c.line_cost || 0), 0);

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.consumedTodayTitle")} subtitle={t("materials.consumedTodaySubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
          <p className="text-2xl font-black">{consumptions.length}</p>
          <p className="text-xs text-[var(--brand-muted)]">{t("materials.consumedTodayCount")}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
          <p className="text-2xl font-black">{totalCost.toLocaleString()}</p>
          <p className="text-xs text-[var(--brand-muted)]">{t("materials.consumedCostToday")}</p>
        </div>
      </div>

      <div className="space-y-2">
        {consumptions.map((c) => (
          <div key={c.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-mono text-sm font-bold">{c.material_code}</p>
                <p className="font-bold">{c.material_name}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {c.job_number} · {c.stage}
                </p>
              </div>
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-800">
                -{formatQty(c.quantity)} {c.material_unit}
              </span>
            </div>
            <div className="mt-2 flex justify-between text-sm">
              <span className="text-[var(--brand-muted)]">{formatDate(c.consumed_at)}</span>
              <strong>{c.line_cost?.toLocaleString()} so'm</strong>
            </div>
          </div>
        ))}
        {!loading && consumptions.length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("materials.consumedTodayEmpty")}</p>
        ) : null}
      </div>
    </div>
  );
}
