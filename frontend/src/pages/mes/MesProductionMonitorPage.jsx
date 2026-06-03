import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import MesMonitorTimeline from "../../components/mes/MesMonitorTimeline";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const MONITOR_STAGES = [
  "Lazer",
  "Svarshik",
  "Kraska",
  "Nazorat",
  "Upakovka",
  "Sklad",
  "Yuklash",
];

const PRIORITIES = ["", "urgent", "high", "normal", "low"];

function ProgressBar({ value }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, backgroundColor: "var(--brand-button)" }}
      />
    </div>
  );
}

function StatCard({ label, value, accent, warn }) {
  return (
    <div
      className={`rounded-2xl border bg-[var(--brand-card)] p-3 sm:p-4 ${
        warn ? "border-red-200" : ""
      }`}
    >
      <p
        className="text-2xl font-black sm:text-3xl"
        style={{ color: warn ? "#dc2626" : accent || "var(--brand-primary)" }}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--brand-muted)] sm:text-sm">{label}</p>
    </div>
  );
}

export default function MesProductionMonitorPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("mes_view") || hasPermission("mes_jobs_view");

  const [dashboard, setDashboard] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [stageFilter, setStageFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const params = {};
      if (stageFilter) params.stage = stageFilter;
      if (customerFilter.trim()) params.customer = customerFilter.trim();
      if (priorityFilter) params.priority = priorityFilter;
      const [dash, jobsRes] = await Promise.all([
        api.mesMonitorDashboard(),
        api.mesMonitorJobs(params),
      ]);
      setDashboard(dash);
      setJobs(jobsRes.jobs || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, stageFilter, customerFilter, priorityFilter]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const customers = useMemo(() => {
    const set = new Set(jobs.map((j) => j.customer_name).filter(Boolean));
    return [...set].sort();
  }, [jobs]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <PageHeader
        title={t("mes.productionMonitor")}
        subtitle={t("mes.productionMonitorSubtitle")}
        actions={
          <button
            type="button"
            onClick={load}
            className="min-h-[44px] rounded-2xl px-5 py-2 text-sm font-semibold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {t("common.refresh")}
          </button>
        }
      />

      {dashboard ? (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
          <StatCard label={t("mes.monitorActiveJobs")} value={dashboard.active_jobs} />
          <StatCard
            label={t("mes.monitorDelayedJobs")}
            value={dashboard.delayed_jobs}
            warn={dashboard.delayed_jobs > 0}
          />
          <StatCard
            label={t("mes.monitorCompletedToday")}
            value={dashboard.completed_today}
            accent="#16a34a"
          />
          <StatCard
            label={t("mes.monitorInProgress")}
            value={dashboard.in_progress}
            accent="#d97706"
          />
        </div>
      ) : null}

      <div className="mb-4 grid gap-2 rounded-2xl border bg-[var(--brand-card)] p-3 sm:grid-cols-3 sm:gap-3 sm:p-4">
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-[var(--brand-muted)]">
            {t("mes.monitorFilterStage")}
          </span>
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="w-full min-h-[44px] rounded-xl border px-3"
          >
            <option value="">{t("mes.allStatuses")}</option>
            {MONITOR_STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-[var(--brand-muted)]">
            {t("mes.customerName")}
          </span>
          <input
            type="text"
            list="monitor-customers"
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
            placeholder={t("mes.searchJobs")}
            className="w-full min-h-[44px] rounded-xl border px-3"
          />
          <datalist id="monitor-customers">
            {customers.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-[var(--brand-muted)]">
            {t("mes.priority")}
          </span>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="w-full min-h-[44px] rounded-xl border px-3"
          >
            <option value="">{t("mes.allStatuses")}</option>
            {PRIORITIES.filter(Boolean).map((p) => (
              <option key={p} value={p}>
                {t(`mes.priority_${p}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && jobs.length === 0 ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {jobs.length === 0 && !loading ? (
        <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
          {t("mes.monitorEmpty")}
        </p>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.id}
              className={`rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm ${
                job.is_delayed ? "border-red-200" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link
                    to={`/mes/jobs/${job.id}`}
                    className="font-mono text-lg font-black text-[var(--brand-primary)] hover:underline"
                  >
                    {job.job_number}
                  </Link>
                  <p className="text-sm font-semibold">
                    {job.template_code} · {job.template_name}
                  </p>
                  <p className="text-xs text-[var(--brand-muted)]">
                    {job.customer_name || "—"}
                    {job.order_reference ? ` · ${job.order_reference}` : ""}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-bold">{t("mes.quantity")}: {job.quantity}</p>
                  <p className="text-[var(--brand-muted)]">
                    {t("mes.dueDate")}:{" "}
                    {job.due_date ? new Date(job.due_date).toLocaleDateString() : "—"}
                  </p>
                  <p className="font-semibold text-amber-700">{job.current_stage}</p>
                </div>
              </div>

              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-xs sm:text-sm">
                  <span>{t("mes.overallProgress")}</span>
                  <span className="font-bold">{Math.round(job.overall_progress_pct || 0)}%</span>
                </div>
                <ProgressBar value={job.overall_progress_pct} />
              </div>

              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold text-[var(--brand-muted)]">
                  {t("mes.routeTimeline")}
                </p>
                <MesMonitorTimeline timeline={job.route_timeline} compact />
                <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-[var(--brand-muted)]">
                  <span>● {t("mes.monitorStatus_waiting")}</span>
                  <span>● {t("mes.monitorStatus_active")}</span>
                  <span>● {t("mes.monitorStatus_completed")}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
