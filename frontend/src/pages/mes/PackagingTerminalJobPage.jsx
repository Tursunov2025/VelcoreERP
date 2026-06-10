import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function ProgressBar({ value, large = false }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className={`w-full overflow-hidden rounded-full bg-gray-200 ${large ? "h-4" : "h-2.5"}`}>
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, backgroundColor: "var(--brand-button)" }}
      />
    </div>
  );
}

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function PackagingTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_packaging");

  const [job, setJob] = useState(null);
  const [form, setForm] = useState({
    package_type: "",
    package_count: "",
    net_weight_kg: "",
    gross_weight_kg: "",
    notes: "",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const data = await api.mesPackagingJob(id);
      setJob(data);
      setForm({
        package_type: data.package_type || "",
        package_count: String(data.package_count || 0),
        net_weight_kg: formatQty(data.net_weight_kg),
        gross_weight_kg: formatQty(data.gross_weight_kg),
        notes: data.notes || "",
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canUse, id]);

  useEffect(() => {
    load();
  }, [load]);

  const stepState = job?.packaging_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterData = stepState === "in_progress";
  const canComplete =
    stepState === "in_progress" &&
    Number(job?.package_count || 0) > 0 &&
    (job?.packages || []).length >= Number(job?.package_count || 0);

  const formDirty = useMemo(() => {
    if (!job) return false;
    return (
      form.package_type !== (job.package_type || "") ||
      form.package_count !== String(job.package_count || 0) ||
      formatQty(form.net_weight_kg) !== formatQty(job.net_weight_kg) ||
      formatQty(form.gross_weight_kg) !== formatQty(job.gross_weight_kg) ||
      form.notes !== (job.notes || "")
    );
  }, [job, form]);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesPackagingAcceptJob(id);
      else if (action === "start") updated = await api.mesPackagingStartJob(id);
      else if (action === "complete") updated = await api.mesPackagingCompleteJob(id);
      setJob(updated);
      setToast(t(`mes.packagingAction_${action}`));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const savePackagingData = async () => {
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesPackagingUpdateData(id, {
        package_type: form.package_type,
        package_count: Number(form.package_count) || 0,
        net_weight_kg: Number(form.net_weight_kg) || 0,
        gross_weight_kg: Number(form.gross_weight_kg) || 0,
        notes: form.notes,
      });
      setJob(updated);
      setForm({
        package_type: updated.package_type || "",
        package_count: String(updated.package_count || 0),
        net_weight_kg: formatQty(updated.net_weight_kg),
        gross_weight_kg: formatQty(updated.gross_weight_kg),
        notes: updated.notes || "",
      });
      setToast(t("mes.packagingDataSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!canUse) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;
  if (!job) return <ErrorAlert message={error || "Not found"} />;

  return (
    <div className="pb-36">
      <BackButton fallback="/mes/terminal/packaging" label={t("mes.packagingTerminal")} className="mb-4" />

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>
            <p className="text-xs font-semibold text-pink-700">{job.packaging_step?.stage_name}</p>
          </div>
          <span className="rounded-full bg-pink-100 px-3 py-1 text-sm font-bold text-pink-900">
            {t(`mes.terminalStep_${stepState}`)}
          </span>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.overallProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
          <p className="mt-1 text-xs text-[var(--brand-muted)]">{t("mes.packagingProgressHint")}</p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.packagingData")}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="sm:col-span-2">
            <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.packageType")}</span>
            <input
              type="text"
              disabled={!canEnterData || isCompleted || busy}
              value={form.package_type}
              onChange={(e) => setForm((f) => ({ ...f, package_type: e.target.value }))}
              className="w-full min-h-[48px] rounded-xl border px-3 text-base font-semibold"
              placeholder={t("mes.packageTypePlaceholder")}
            />
          </label>
          <label>
            <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.packageCount")}</span>
            <input
              type="number"
              min="0"
              step="1"
              disabled={!canEnterData || isCompleted || busy}
              value={form.package_count}
              onChange={(e) => setForm((f) => ({ ...f, package_count: e.target.value }))}
              className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
            />
          </label>
          <label>
            <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.netWeightKg")}</span>
            <input
              type="number"
              min="0"
              step="any"
              disabled={!canEnterData || isCompleted || busy}
              value={form.net_weight_kg}
              onChange={(e) => setForm((f) => ({ ...f, net_weight_kg: e.target.value }))}
              className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
            />
          </label>
          <label>
            <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.grossWeightKg")}</span>
            <input
              type="number"
              min="0"
              step="any"
              disabled={!canEnterData || isCompleted || busy}
              value={form.gross_weight_kg}
              onChange={(e) => setForm((f) => ({ ...f, gross_weight_kg: e.target.value }))}
              className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
            />
          </label>
          <label className="sm:col-span-2">
            <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("common.notes")}</span>
            <textarea
              rows={2}
              disabled={!canEnterData || isCompleted || busy}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              className="w-full rounded-xl border px-3 py-2"
            />
          </label>
        </div>

        {canEnterData && formDirty ? (
          <button
            type="button"
            disabled={busy}
            onClick={savePackagingData}
            className="mt-4 w-full min-h-[52px] rounded-2xl text-base font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {busy ? t("common.saving") : t("mes.savePackagingData")}
          </button>
        ) : null}
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h3 className="text-lg font-bold">{t("mes.packageLabels")}</h3>
          <div className="text-sm text-[var(--brand-muted)]">
            <span className="mr-4 font-bold text-[var(--brand-primary)]">
              {t("mes.packageCount")}: {job.package_count ?? 0}
            </span>
            <span className="mr-4">{t("mes.totalNetKg")}: {formatQty(job.total_net_weight_kg)}</span>
            <span>{t("mes.totalGrossKg")}: {formatQty(job.total_gross_weight_kg)}</span>
          </div>
        </div>

        {(job.packages || []).length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.noPackagesYet")}</p>
        ) : (
          <div className="space-y-2">
            {(job.packages || []).map((pkg) => (
              <div key={pkg.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-mono text-base font-black">{pkg.package_number}</p>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                      pkg.status === "packed"
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {t(`mes.packageStatus_${pkg.status}`)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-[var(--brand-muted)]">{pkg.package_type || "—"}</p>
                <p className="mt-2 text-sm">
                  {t("mes.netWeightKg")}: {formatQty(pkg.net_weight_kg)} · {t("mes.grossWeightKg")}:{" "}
                  {formatQty(pkg.gross_weight_kg)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {!isCompleted ? (
        <div className="fixed bottom-0 left-0 right-0 z-30 border-t bg-[var(--brand-card)] p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-lg md:static md:mt-4 md:rounded-2xl md:border md:p-4 md:shadow-none">
          <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row">
            {canAccept ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("accept")}
                className="min-h-[52px] flex-1 rounded-2xl text-base font-bold text-white disabled:opacity-60"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("mes.packagingAccept")}
              </button>
            ) : null}
            {canStart ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("start")}
                className="min-h-[52px] flex-1 rounded-2xl text-base font-bold text-white disabled:opacity-60"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("mes.packagingStart")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.packagingComplete")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.packagingStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
