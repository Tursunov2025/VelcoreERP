import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import MesRouteTimeline from "../../components/mes/MesRouteTimeline";
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

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function MesJobDetailPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView =
    isAdmin || hasPermission("mes_view") || hasPermission("mes_jobs_view");
  const canManage =
    isAdmin || hasPermission("mes_edit") || hasPermission("mes_jobs_manage");
  const canMaterials = isAdmin || hasPermission("materials_view");

  const [job, setJob] = useState(null);
  const [materialCost, setMaterialCost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.mesGetJob(id);
      setJob(data);
      if (canMaterials && data.status !== "draft") {
        try {
          const cost = await api.materialsJobMaterialCost(id);
          setMaterialCost(cost);
        } catch {
          setMaterialCost(null);
        }
      } else {
        setMaterialCost(null);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, canMaterials, id]);

  useEffect(() => {
    load();
  }, [load]);

  const release = async () => {
    if (!window.confirm(t("mes.confirmRelease"))) return;
    try {
      const updated = await api.mesReleaseJob(id);
      setJob(updated);
      setToast(t("mes.jobReleased"));
    } catch (err) {
      setToast(err.message);
    }
  };

  const setStatus = async (status) => {
    try {
      const updated = await api.mesUpdateJobStatus(id, status);
      setJob(updated);
      setToast(t("mes.statusUpdated"));
    } catch (err) {
      setToast(err.message);
    }
  };

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;
  if (!job) return <ErrorAlert message={error || "Not found"} />;

  const routeForTimeline = {
    name: job.route_name || t("mes.routeSnapshot"),
    version: job.route_version || 1,
    is_default: true,
    estimated_total_minutes: (job.route_steps || []).reduce(
      (sum, s) => sum + (s.estimated_minutes || 0),
      0
    ),
    steps: (job.route_steps || []).map((step) => ({
      ...step,
      stage_color: null,
    })),
  };

  const statusActions = {
    draft: canManage ? [{ status: "cancelled", label: t("mes.cancelJob") }] : [],
    released: canManage
      ? [
          { status: "in_progress", label: t("mes.startJob"), primary: true },
          { status: "on_hold", label: t("mes.holdJob") },
          { status: "cancelled", label: t("mes.cancelJob") },
        ]
      : [],
    in_progress: canManage
      ? [
          { status: "on_hold", label: t("mes.holdJob") },
          { status: "completed", label: t("mes.completeJob"), primary: true },
          { status: "cancelled", label: t("mes.cancelJob") },
        ]
      : [],
    on_hold: canManage
      ? [
          { status: "in_progress", label: t("mes.resumeJob"), primary: true },
          { status: "cancelled", label: t("mes.cancelJob") },
        ]
      : [],
  };

  const actions = statusActions[job.status] || [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <BackButton fallback="/mes/jobs" label={t("mes.jobsTitle")} />
        <div className="flex flex-wrap gap-2">
          {job.status === "draft" && canManage && (
            <>
              <Link
                to={`/mes/jobs/${id}/edit`}
                className="rounded-xl border px-4 py-2 text-sm font-semibold"
              >
                {t("mes.editJob")}
              </Link>
              <button
                type="button"
                onClick={release}
                className="rounded-xl px-4 py-2 text-sm font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("mes.releaseJob")}
              </button>
            </>
          )}
          {actions.map((action) => (
            <button
              key={action.status}
              type="button"
              onClick={() => setStatus(action.status)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                action.primary
                  ? "text-white"
                  : action.status === "cancelled"
                    ? "border border-red-200 text-red-600"
                    : "border"
              }`}
              style={action.primary ? { backgroundColor: "var(--brand-button)" } : undefined}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <PageHeader
        title={job.job_number}
        subtitle={`${job.template_code} · ${job.template_name}`}
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-3 py-1 text-sm font-bold ${
            STATUS_CLASS[job.status] || STATUS_CLASS.draft
          }`}
        >
          {t(`mes.jobStatus_${job.status}`)}
        </span>
        <span className="text-sm text-[var(--brand-muted)] capitalize">
          {t("mes.priority")}: {t(`mes.priority_${job.priority}`)}
        </span>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <p className="text-sm text-[var(--brand-muted)]">{t("mes.product")}</p>
          <p className="font-mono font-bold">{job.template_code}</p>
          <p className="text-sm">{job.template_name}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <p className="text-sm text-[var(--brand-muted)]">{t("mes.quantity")}</p>
          <p className="text-3xl font-black">{formatQty(job.quantity)}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <p className="text-sm text-[var(--brand-muted)]">{t("mes.customerName")}</p>
          <p className="font-semibold">{job.customer_name || "—"}</p>
          <p className="text-xs text-[var(--brand-muted)]">{job.order_reference || "—"}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <p className="text-sm text-[var(--brand-muted)]">{t("mes.dueDate")}</p>
          <p className="font-semibold">
            {job.due_date ? new Date(job.due_date).toLocaleDateString() : "—"}
          </p>
          {job.started_at && (
            <p className="mt-1 text-xs text-[var(--brand-muted)]">
              {t("mes.startedAt")}: {new Date(job.started_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {canMaterials && job.status !== "draft" ? (
        <div className="mb-6 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
          <h3 className="mb-3 text-lg font-bold">{t("materials.jobMaterialCost")}</h3>
          {!materialCost || (materialCost.lines || []).length === 0 ? (
            <p className="text-sm text-[var(--brand-muted)]">{t("materials.jobMaterialCostEmpty")}</p>
          ) : (
            <>
              <p className="mb-4 text-2xl font-black">
                {t("materials.jobMaterialCostTotal")}: {materialCost.total_cost?.toLocaleString()} {t("dashboard.currency")}
              </p>
              <div className="space-y-2">
                {materialCost.lines.map((line) => (
                  <div key={line.id} className="flex flex-wrap items-center justify-between rounded-xl border p-3 text-sm">
                    <div>
                      <p className="font-mono font-bold">{line.material_code}</p>
                      <p>{line.material_name}</p>
                      <p className="text-xs text-[var(--brand-muted)]">
                        {line.stage} · {formatQty(line.quantity)} {line.material_unit}
                      </p>
                    </div>
                    <strong>{line.line_cost?.toLocaleString()}</strong>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ) : null}

      <div className="mb-6 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.bomSnapshot")}</h3>
        {(job.bom_lines || []).length === 0 ? (
          <p className="py-6 text-center text-[var(--brand-muted)]">{t("mes.noSnapshotYet")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b text-[var(--brand-muted)]">
                  <th className="px-2 py-2">#</th>
                  <th className="px-2 py-2">{t("mes.partNumber")}</th>
                  <th className="px-2 py-2">{t("mes.name")}</th>
                  <th className="px-2 py-2">{t("mes.allocatedQty")}</th>
                  <th className="px-2 py-2">{t("mes.completedQty")}</th>
                  <th className="px-2 py-2">{t("mes.acceptedQty")}</th>
                  <th className="px-2 py-2">{t("mes.rejectedQty")}</th>
                </tr>
              </thead>
              <tbody>
                {(job.bom_lines || []).map((line, index) => (
                  <tr key={line.id} className="border-b">
                    <td className="px-2 py-2">{index + 1}</td>
                    <td className="px-2 py-2 font-mono font-semibold">{line.part_number}</td>
                    <td className="px-2 py-2">{line.part_name}</td>
                    <td className="px-2 py-2">{formatQty(line.allocated_quantity)}</td>
                    <td className="px-2 py-2">{formatQty(line.completed_quantity)}</td>
                    <td className="px-2 py-2">{formatQty(line.accepted_quantity)}</td>
                    <td className="px-2 py-2">{formatQty(line.rejected_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mb-6">
        <h3 className="mb-3 text-lg font-bold">{t("mes.routeSnapshot")}</h3>
        {(job.route_steps || []).length === 0 ? (
          <p className="rounded-2xl border bg-[var(--brand-card)] py-8 text-center text-[var(--brand-muted)]">
            {t("mes.noSnapshotYet")}
          </p>
        ) : (
          <MesRouteTimeline route={routeForTimeline} compact />
        )}
      </div>

      {error && <ErrorAlert message={error} />}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
