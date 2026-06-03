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
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
      <p className="text-3xl font-black" style={{ color: accent || "var(--brand-primary)" }}>
        {value}
      </p>
      <p className="mt-1 text-sm text-[var(--brand-muted)]">{label}</p>
    </div>
  );
}

export default function SvarshikTerminalQueuePage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_svarshik");

  const [data, setData] = useState({ jobs: [], stages: [], active_jobs: 0, waiting_jobs: 0, completed_today: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const [queue, dashboard] = await Promise.all([
        api.mesSvarshikQueue(),
        api.mesSvarshikDashboard(),
      ]);
      setData({
        jobs: queue.jobs || [],
        stages: queue.stages || [],
        active_jobs: dashboard.active_jobs ?? 0,
        waiting_jobs: dashboard.waiting_jobs ?? 0,
        completed_today: dashboard.completed_today ?? 0,
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
        title={t("mes.svarshikTerminal")}
        subtitle={t("mes.svarshikQueueSubtitle")}
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

      <div className="mb-4 grid grid-cols-3 gap-2 sm:gap-3">
        <StatCard label={t("mes.svarshikActiveJobs")} value={data.active_jobs} accent="#d97706" />
        <StatCard label={t("mes.svarshikWaitingJobs")} value={data.waiting_jobs} />
        <StatCard label={t("mes.svarshikCompletedToday")} value={data.completed_today} accent="#16a34a" />
      </div>

      {loading && data.jobs.length === 0 ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {data.jobs.length === 0 && !loading ? (
        <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
          {t("mes.svarshikQueueEmpty")}
        </p>
      ) : (
        <div className="space-y-3">
          {data.jobs.map((job) => (
            <Link
              key={job.id}
              to={`/mes/terminal/svarshik/jobs/${job.id}`}
              className="block rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm active:scale-[0.99]"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-lg font-black">{job.job_number}</p>
                  <p className="text-sm font-semibold">
                    {job.template_code} · {job.template_name}
                  </p>
                  <p className="text-xs text-[var(--brand-muted)]">
                    {job.welding_step?.stage_name || t("mes.svarshikTerminal")}
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
      )}
    </div>
  );
}
