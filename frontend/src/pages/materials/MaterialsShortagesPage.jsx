import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function MaterialsShortagesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");

  const [data, setData] = useState({
    shortage_count: 0,
    materials_planned: 0,
    total_required: 0,
    shortages: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const result = await api.materialsPlanningShortages();
      setData(result);
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

  const shortages = data.shortages || [];

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.shortagesTitle")} subtitle={t("materials.shortagesSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3 text-center">
          <p className="text-2xl font-black text-red-600">{data.shortage_count ?? 0}</p>
          <p className="text-xs text-[var(--brand-muted)]">{t("materials.shortageItems")}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3 text-center">
          <p className="text-2xl font-black">{data.materials_planned ?? 0}</p>
          <p className="text-xs text-[var(--brand-muted)]">{t("materials.materialsPlanned")}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3 text-center">
          <p className="text-2xl font-black">{formatQty(data.total_required)}</p>
          <p className="text-xs text-[var(--brand-muted)]">{t("materials.totalRequired")}</p>
        </div>
      </div>

      <div className="space-y-2">
        {shortages.map((row) => (
          <div
            key={row.material_id}
            className={`rounded-xl border p-4 ${
              row.shortage_quantity > 0 ? "border-red-300 bg-red-50/40" : "bg-[var(--brand-card)]"
            }`}
          >
            <p className="font-mono text-sm font-bold">{row.material_code}</p>
            <p className="font-bold">{row.material_name}</p>
            <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-[var(--brand-muted)]">{t("materials.required")}</p>
                <p className="font-bold">
                  {formatQty(row.required_quantity)} {row.material_unit}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--brand-muted)]">{t("materials.available")}</p>
                <p className="font-bold">
                  {formatQty(row.available_quantity)} {row.material_unit}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--brand-muted)]">{t("materials.shortage")}</p>
                <p className={`font-bold ${row.shortage_quantity > 0 ? "text-red-600" : ""}`}>
                  {formatQty(row.shortage_quantity)} {row.material_unit}
                </p>
              </div>
            </div>
            {row.jobs?.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {row.jobs.map((j) => (
                  <span
                    key={`${row.material_id}-${j.job_id}`}
                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-mono"
                  >
                    {j.job_number}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {!loading && shortages.length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("materials.noShortages")}</p>
        ) : null}
      </div>
    </div>
  );
}
