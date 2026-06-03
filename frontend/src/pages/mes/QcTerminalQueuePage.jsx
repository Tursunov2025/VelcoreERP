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

const REWORK_STATUS_CLASS = {
  pending: "bg-orange-100 text-orange-900",
  in_progress: "bg-amber-100 text-amber-900",
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

export default function QcTerminalQueuePage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_qc");
  const canEditReasons = isAdmin || hasPermission("mes_edit");

  const [data, setData] = useState({
    jobs: [],
    reworkRecords: [],
    waiting_jobs: 0,
    active_inspections: 0,
    rework_jobs: 0,
    completed_today: 0,
  });
  const [tab, setTab] = useState("queue");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const [queue, dashboard, rework] = await Promise.all([
        api.mesQcQueue(),
        api.mesQcDashboard(),
        api.mesQcReworkQueue(),
      ]);
      setData({
        jobs: queue.jobs || [],
        reworkRecords: rework.records || [],
        waiting_jobs: dashboard.waiting_jobs ?? 0,
        active_inspections: dashboard.active_inspections ?? 0,
        rework_jobs: dashboard.rework_jobs ?? 0,
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
        title={t("mes.qcTerminal")}
        subtitle={t("mes.qcQueueSubtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            {canEditReasons ? (
              <Link
                to="/mes/qc/rejection-reasons"
                className="min-h-[44px] rounded-2xl border px-4 py-2 text-sm font-semibold"
              >
                {t("mes.qcRejectionReasons")}
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
        <StatCard label={t("mes.qcWaitingJobs")} value={data.waiting_jobs} />
        <StatCard label={t("mes.qcActiveInspections")} value={data.active_inspections} accent="#d97706" />
        <StatCard label={t("mes.qcReworkJobs")} value={data.rework_jobs} accent="#ea580c" />
        <StatCard label={t("mes.qcCompletedToday")} value={data.completed_today} accent="#16a34a" />
      </div>

      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("queue")}
          className={`min-h-[44px] flex-1 rounded-2xl text-sm font-bold ${
            tab === "queue" ? "text-white" : "border bg-[var(--brand-card)]"
          }`}
          style={tab === "queue" ? { backgroundColor: "var(--brand-button)" } : undefined}
        >
          {t("mes.qcTabQueue")} ({data.jobs.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("rework")}
          className={`min-h-[44px] flex-1 rounded-2xl text-sm font-bold ${
            tab === "rework" ? "text-white" : "border bg-[var(--brand-card)]"
          }`}
          style={tab === "rework" ? { backgroundColor: "var(--brand-button)" } : undefined}
        >
          {t("mes.qcTabRework")} ({data.reworkRecords.length})
        </button>
      </div>

      {loading && data.jobs.length === 0 && tab === "queue" ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {tab === "queue" ? (
        data.jobs.length === 0 && !loading ? (
          <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
            {t("mes.qcQueueEmpty")}
          </p>
        ) : (
          <div className="space-y-3">
            {data.jobs.map((job) => (
              <Link
                key={job.id}
                to={`/mes/terminal/qc/jobs/${job.id}`}
                className="block rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm active:scale-[0.99]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-lg font-black">{job.job_number}</p>
                    <p className="text-sm font-semibold">
                      {job.template_code} · {job.template_name}
                    </p>
                    <p className="text-xs text-[var(--brand-muted)]">
                      {job.qc_step?.stage_name || t("mes.qcTerminal")}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                        STEP_STATE_CLASS[job.step_state] || STEP_STATE_CLASS.pending_accept
                      }`}
                    >
                      {t(`mes.terminalStep_${job.step_state}`)}
                    </span>
                    {job.open_rework_count > 0 ? (
                      <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-800">
                        {t("mes.qcOpenRework")}: {job.open_rework_count}
                      </span>
                    ) : null}
                  </div>
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
      ) : data.reworkRecords.length === 0 && !loading ? (
        <p className="rounded-2xl border bg-[var(--brand-card)] py-16 text-center text-[var(--brand-muted)]">
          {t("mes.qcReworkEmpty")}
        </p>
      ) : (
        <div className="space-y-3">
          {data.reworkRecords.map((record) => (
            <Link
              key={record.id}
              to={`/mes/terminal/qc/jobs/${record.job_id}`}
              className="block rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm active:scale-[0.99]"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono font-bold">{record.part_number}</p>
                  <p className="text-sm">{record.part_name}</p>
                  <p className="mt-1 text-xs text-[var(--brand-muted)]">
                    {record.rejection_reason_name || t("mes.qcNoReason")}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                    REWORK_STATUS_CLASS[record.status] || REWORK_STATUS_CLASS.pending
                  }`}
                >
                  {t(`mes.qcReworkStatus_${record.status}`)}
                </span>
              </div>
              <p className="mt-2 text-sm font-bold">
                {t("mes.reworkQty")}: {record.quantity}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
