import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const TYPE_CLASS = {
  receipt: "text-green-700 bg-green-50",
  issue: "text-orange-700 bg-orange-50",
  adjustment: "text-blue-700 bg-blue-50",
};

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

export default function MaterialsMovementsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");

  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.materialsMovements();
      setMovements(data.movements || []);
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

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.movementsTitle")} subtitle={t("materials.movementsSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-2">
        {movements.map((m) => (
          <div key={m.id} className="rounded-xl border bg-[var(--brand-card)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-bold">
                  {m.material_code} — {m.material_name}
                </p>
                <p className="text-sm text-[var(--brand-muted)]">{formatDate(m.created_at)}</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${
                  TYPE_CLASS[m.movement_type] || "bg-gray-100"
                }`}
              >
                {t(`materials.movementType.${m.movement_type}`) || m.movement_type}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldQuantity")}: </span>
                <strong>{m.quantity}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.balanceAfter")}: </span>
                <strong>{m.balance_after}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldUnitCost")}: </span>
                <strong>{m.unit_cost?.toLocaleString()}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("common.user")}: </span>
                <strong>{m.created_by}</strong>
              </div>
            </div>
            {m.notes ? <p className="mt-1 text-xs text-[var(--brand-muted)]">{m.notes}</p> : null}
          </div>
        ))}
        {!loading && movements.length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("materials.movementsEmpty")}</p>
        ) : null}
      </div>
    </div>
  );
}
