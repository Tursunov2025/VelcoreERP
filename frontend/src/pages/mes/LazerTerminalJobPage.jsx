import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
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

export default function LazerTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_lazer");

  const [job, setJob] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const data = await api.mesLazerJob(id);
      setJob(data);
      const next = {};
      (data.laser_parts || data.bom_lines || []).forEach((line) => {
        next[line.id] = formatQty(line.completed_quantity);
      });
      setQuantities(next);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canUse, id]);

  useEffect(() => {
    load();
  }, [load]);

  const stepState = job?.lazer_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";

  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterQty = stepState === "in_progress";
  const canComplete =
    stepState === "in_progress" && Number(job?.overall_progress_pct || 0) >= 100;

  const dirtyLines = useMemo(() => {
    if (!job?.laser_parts) return [];
    return job.laser_parts.filter((line) => {
      const current = formatQty(line.completed_quantity);
      const draft = quantities[line.id] ?? current;
      return draft !== current;
    });
  }, [job, quantities]);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesLazerAcceptJob(id);
      else if (action === "start") updated = await api.mesLazerStartJob(id);
      else if (action === "complete") updated = await api.mesLazerCompleteJob(id);
      setJob(updated);
      setToast(t(`mes.lazerAction_${action}`));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveQuantities = async () => {
    if (!dirtyLines.length) return;
    setBusy(true);
    setToast("");
    try {
      const lines = dirtyLines.map((line) => ({
        bom_line_id: line.id,
        completed_quantity: Number(quantities[line.id] ?? line.completed_quantity),
      }));
      const updated = await api.mesLazerUpdateQuantities(id, lines);
      setJob(updated);
      if (updated.auto_completed) {
        setToast(t("mes.lazerAutoCompleted"));
      } else {
        setToast(t("mes.lazerQtySaved"));
      }
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
      <Link
        to="/mes/terminal/lazer"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.lazerTerminal")}
      </Link>

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>
          </div>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-bold text-amber-900">
            {t(`mes.lazerStep_${stepState}`)}
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border p-3">
            <p className="text-xs text-[var(--brand-muted)]">{t("mes.quantity")}</p>
            <p className="text-2xl font-black">{formatQty(job.quantity)}</p>
          </div>
          <div className="rounded-xl border p-3">
            <p className="text-xs text-[var(--brand-muted)]">{t("mes.customerName")}</p>
            <p className="font-semibold">{job.customer_name || "—"}</p>
            <p className="text-xs text-[var(--brand-muted)]">{job.order_reference || "—"}</p>
          </div>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.overallProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-1 text-lg font-bold">{t("mes.laserParts")}</h3>
        <p className="mb-4 text-sm text-[var(--brand-muted)]">{t("mes.laserPartsHint")}</p>

        {(job.laser_parts || []).length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.noSnapshotYet")}</p>
        ) : (
          <div className="space-y-4">
            {(job.laser_parts || []).map((line) => (
              <div key={line.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono font-bold">{line.part_number}</p>
                    <p className="text-sm">{line.part_name}</p>
                  </div>
                  <span className="text-sm font-bold">{Math.round(line.progress_pct || 0)}%</span>
                </div>
                <div className="mt-2">
                  <ProgressBar value={line.progress_pct} />
                </div>
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <label className="flex-1 min-w-[140px]">
                    <span className="mb-1 block text-xs text-[var(--brand-muted)]">
                      {t("mes.completedQty")} / {formatQty(line.allocated_quantity)} {line.unit}
                    </span>
                    <input
                      type="number"
                      min="0"
                      max={line.allocated_quantity}
                      step="any"
                      disabled={!canEnterQty || isCompleted || busy}
                      value={quantities[line.id] ?? formatQty(line.completed_quantity)}
                      onChange={(e) =>
                        setQuantities((prev) => ({ ...prev, [line.id]: e.target.value }))
                      }
                      className="w-full min-h-[48px] rounded-xl border px-4 text-lg font-bold"
                    />
                  </label>
                  {line.drawing_url ? (
                    <a
                      href={line.drawing_url}
                      target="_blank"
                      rel="noreferrer"
                      className="min-h-[48px] rounded-xl border px-4 py-3 text-sm font-semibold"
                    >
                      {t("mes.openDrawing")}
                    </a>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}

        {canEnterQty && dirtyLines.length > 0 ? (
          <button
            type="button"
            disabled={busy}
            onClick={saveQuantities}
            className="mt-4 w-full min-h-[52px] rounded-2xl text-base font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {busy ? t("common.saving") : t("mes.saveQuantities")}
          </button>
        ) : null}
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
                {t("mes.lazerAccept")}
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
                {t("mes.lazerStartWork")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.lazerCompleteWork")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.lazerStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
