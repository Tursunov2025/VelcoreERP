import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const STATUS_CLASS = {
  draft: "bg-gray-200 text-gray-800",
  released: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-900",
  on_hold: "bg-orange-100 text-orange-900",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

export default function MesJobsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView =
    isAdmin || hasPermission("mes_view") || hasPermission("mes_jobs_view");
  const canManage =
    isAdmin || hasPermission("mes_edit") || hasPermission("mes_jobs_manage");

  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.mesGetJobs({
        q: debouncedSearch,
        status: statusFilter || undefined,
      });
      setJobs(data.jobs || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, debouncedSearch, statusFilter]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link to="/mes" className="text-sm text-[var(--brand-primary)] hover:underline">
          ← {t("mes.backHub")}
        </Link>
        {canManage && (
          <Link
            to="/mes/jobs/new"
            className="rounded-xl px-4 py-2 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            + {t("mes.addJob")}
          </Link>
        )}
      </div>

      <PageHeader title={t("mes.jobsTitle")} subtitle={t("mes.jobsSubtitle")} />

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("mes.searchJobs")}
          className="min-w-[200px] flex-1 rounded-xl border px-4 py-2"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border px-4 py-2"
        >
          <option value="">{t("mes.allStatuses")}</option>
          {["draft", "released", "in_progress", "on_hold", "completed", "cancelled"].map(
            (s) => (
              <option key={s} value={s}>
                {t(`mes.jobStatus_${s}`)}
              </option>
            )
          )}
        </select>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : jobs.length === 0 ? (
        <p className="py-12 text-center text-[var(--brand-muted)]">{t("mes.emptyJobs")}</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-[var(--brand-card)]">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b text-[var(--brand-muted)]">
                <th className="px-4 py-3">{t("mes.jobNumber")}</th>
                <th className="px-4 py-3">{t("mes.product")}</th>
                <th className="px-4 py-3">{t("mes.customerName")}</th>
                <th className="px-4 py-3">{t("mes.quantity")}</th>
                <th className="px-4 py-3">{t("mes.priority")}</th>
                <th className="px-4 py-3">{t("mes.jobStatus")}</th>
                <th className="px-4 py-3">{t("mes.dueDate")}</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b hover:bg-gray-50/50">
                  <td className="px-4 py-3">
                    <Link
                      to={`/mes/jobs/${job.id}`}
                      className="font-mono font-bold text-[var(--brand-primary)] hover:underline"
                    >
                      {job.job_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs">{job.template_code}</span>
                    <br />
                    {job.template_name}
                  </td>
                  <td className="px-4 py-3">{job.customer_name || "—"}</td>
                  <td className="px-4 py-3">{job.quantity}</td>
                  <td className="px-4 py-3 capitalize">{job.priority}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        STATUS_CLASS[job.status] || STATUS_CLASS.draft
                      }`}
                    >
                      {t(`mes.jobStatus_${job.status}`)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {job.due_date ? new Date(job.due_date).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error && <ErrorAlert message={error} />}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
