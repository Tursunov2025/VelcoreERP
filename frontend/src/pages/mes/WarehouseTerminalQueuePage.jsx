import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const STEP_STATE_CLASS = {
  pending_accept: "bg-gray-200 text-gray-800",
  accepted: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-900",
};

const PRIORITY_CLASS = {
  urgent: "text-red-600",
  high: "text-orange-600",
  normal: "text-[var(--brand-muted)]",
  low: "text-gray-500",
};

function ProgressBar({ value }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, backgroundColor: "var(--brand-button)" }}
      />
    </div>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-3 text-center sm:p-4">
      <p className="text-2xl font-black sm:text-3xl" style={{ color: accent || "var(--brand-primary)" }}>
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--brand-muted)] sm:text-sm">{label}</p>
    </div>
  );
}

export default function WarehouseTerminalQueuePage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_warehouse");
  const canEditLocations = isAdmin || hasPermission("mes_edit");

  const [tab, setTab] = useState("receipts");
  const [data, setData] = useState({
    jobs: [],
    inventory: [],
    waiting_receipts: 0,
    active_placements: 0,
    inventory_items: 0,
    received_today: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const [queue, dashboard, inventory] = await Promise.all([
        api.mesWarehouseQueue(),
        api.mesWarehouseDashboard(),
        api.mesWarehouseInventory(),
      ]);
      setData({
        jobs: queue.jobs || [],
        inventory: inventory.items || [],
        waiting_receipts: dashboard.waiting_receipts ?? 0,
        active_placements: dashboard.active_placements ?? 0,
        inventory_items: dashboard.inventory_items ?? 0,
        received_today: dashboard.received_today ?? 0,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canUse]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!canUse) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <PageHeader
        title={t("mes.warehouseTerminal")}
        subtitle={t("mes.warehouseQueueSubtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            {canEditLocations ? (
              <Link
                to="/mes/warehouse/locations"
                className="min-h-[44px] rounded-2xl border px-4 py-2 text-sm font-semibold"
              >
                {t("mes.warehouseLocations")}
              </Link>
            ) : null}
            <button
              type="button"
              onClick={load}
              className="min-h-[44px] rounded-2xl px-5 py-2 text-sm font-semibold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {t("common.refresh")}
            </button>
          </div>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
        <StatCard label={t("mes.warehouseWaitingReceipts")} value={data.waiting_receipts} />
        <StatCard label={t("mes.warehouseActivePlacements")} value={data.active_placements} accent="#d97706" />
        <StatCard label={t("mes.warehouseInventoryItems")} value={data.inventory_items} accent="#7c3aed" />
        <StatCard label={t("mes.warehouseReceivedToday")} value={data.received_today} accent="#16a34a" />
      </div>

      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("receipts")}
          className={`min-h-[44px] flex-1 rounded-2xl text-sm font-bold ${
            tab === "receipts" ? "text-white" : "border bg-[var(--brand-card)]"
          }`}
          style={tab === "receipts" ? { backgroundColor: "var(--brand-button)" } : undefined}
        >
          {t("mes.warehouseTabReceipts")} ({data.jobs.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("inventory")}
          className={`min-h-[44px] flex-1 rounded-2xl text-sm font-bold ${
            tab === "inventory" ? "text-white" : "border bg-[var(--brand-card)]"
          }`}
          style={tab === "inventory" ? { backgroundColor: "var(--brand-button)" } : undefined}
        >
          {t("mes.warehouseTabInventory")} ({data.inventory.length})
        </button>
      </div>

      {loading && tab === "receipts" && data.jobs.length === 0 ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {tab === "receipts" ? (
        data.jobs.length === 0 && !loading ? (
          <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
            {t("mes.warehouseQueueEmpty")}
          </p>
        ) : (
          <div className="space-y-3">
            {data.jobs.map((job) => (
              <Link
                key={job.id}
                to={`/mes/terminal/warehouse/jobs/${job.id}`}
                className="block rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm active:scale-[0.99]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-lg font-black">{job.job_number}</p>
                    <p className="text-sm font-semibold">
                      {job.template_code} · {job.template_name}
                    </p>
                    <p className="text-xs text-[var(--brand-muted)]">
                      {job.package_total} {t("mes.packagesLabel")} · {job.packages_placed}/{job.package_total}{" "}
                      {t("mes.placedLabel")}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                      STEP_STATE_CLASS[job.step_state] || STEP_STATE_CLASS.pending_accept
                    }`}
                  >
                    {t(`mes.terminalStep_${job.step_state}`)}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between gap-2 text-sm">
                  <span className={PRIORITY_CLASS[job.priority] || PRIORITY_CLASS.normal}>
                    {t(`mes.priority_${job.priority}`)}
                  </span>
                  <span className="font-bold">{Math.round(job.overall_progress_pct || 0)}%</span>
                </div>
                <div className="mt-2">
                  <ProgressBar value={job.overall_progress_pct} />
                </div>
              </Link>
            ))}
          </div>
        )
      ) : data.inventory.length === 0 && !loading ? (
        <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
          {t("mes.warehouseInventoryEmpty")}
        </p>
      ) : (
        <div className="space-y-3">
          {data.inventory.map((item) => (
            <div key={`${item.template_id}-${item.product_code}`} className="rounded-2xl border bg-[var(--brand-card)] p-4">
              <p className="font-mono font-bold">{item.product_code}</p>
              <p className="text-sm font-semibold">{item.product_name}</p>
              <p className="mt-2 text-sm">
                {t("mes.quantity")}: <span className="font-bold">{item.quantity}</span> {item.unit}
              </p>
              <p className="mt-1 text-xs text-[var(--brand-muted)]">
                {t("mes.locations")}: {(item.locations || []).join(", ") || "—"}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
