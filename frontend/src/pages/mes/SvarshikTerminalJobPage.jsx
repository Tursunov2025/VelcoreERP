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

const QTY_FIELDS = ["completed_quantity", "accepted_quantity", "rejected_quantity"];

export default function SvarshikTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_svarshik");

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
      const data = await api.mesSvarshikJob(id);
      setJob(data);
      const next = {};
      (data.welding_parts || data.bom_lines || []).forEach((line) => {
        next[line.id] = {
          completed_quantity: formatQty(line.completed_quantity),
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
        };
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

  const stepState = job?.welding_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterQty = stepState === "in_progress";
  const canComplete =
    stepState === "in_progress" && Number(job?.overall_progress_pct || 0) >= 100;

  const dirtyLines = useMemo(() => {
    if (!job?.welding_parts) return [];
    return job.welding_parts.filter((line) => {
      const draft = quantities[line.id] || {};
      return QTY_FIELDS.some(
        (field) => formatQty(line[field]) !== (draft[field] ?? formatQty(line[field]))
      );
    });
  }, [job, quantities]);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesSvarshikAcceptJob(id);
      else if (action === "start") updated = await api.mesSvarshikStartJob(id);
      else if (action === "complete") updated = await api.mesSvarshikCompleteJob(id);
      setJob(updated);
      setToast(t(`mes.svarshikAction_${action}`));
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
      const lines = dirtyLines.map((line) => {
        const draft = quantities[line.id] || {};
        const payload = { bom_line_id: line.id };
        QTY_FIELDS.forEach((field) => {
          const val = draft[field] ?? formatQty(line[field]);
          if (formatQty(line[field]) !== val) {
            payload[field] = Number(val);
          }
        });
        return payload;
      });
      const updated = await api.mesSvarshikUpdateQuantities(id, lines);
      setJob(updated);
      const next = {};
      (updated.welding_parts || []).forEach((line) => {
        next[line.id] = {
          completed_quantity: formatQty(line.completed_quantity),
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
        };
      });
      setQuantities(next);
      setToast(updated.auto_completed ? t("mes.svarshikAutoCompleted") : t("mes.svarshikQtySaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const setQty = (lineId, field, value) => {
    setQuantities((prev) => ({
      ...prev,
      [lineId]: { ...prev[lineId], [field]: value },
    }));
  };

  if (!canUse) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;
  if (!job) return <ErrorAlert message={error || "Not found"} />;

  return (
    <div className="pb-36">
      <Link
        to="/mes/terminal/svarshik"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.svarshikTerminal")}
      </Link>

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>
            <p className="text-xs font-semibold text-orange-700">
              {job.welding_step?.stage_name}
            </p>
          </div>
          <span className="rounded-full bg-orange-100 px-3 py-1 text-sm font-bold text-orange-900">
            {t(`mes.terminalStep_${stepState}`)}
          </span>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.overallProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
          <p className="mt-1 text-xs text-[var(--brand-muted)]">{t("mes.svarshikProgressHint")}</p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.weldingParts")}</h3>

        {(job.welding_parts || []).length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.noSnapshotYet")}</p>
        ) : (
          <div className="space-y-4">
            {(job.welding_parts || []).map((line) => (
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
                <p className="mt-2 text-xs text-[var(--brand-muted)]">
                  {t("mes.allocatedQty")}: {formatQty(line.allocated_quantity)} {line.unit}
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {QTY_FIELDS.map((field) => (
                    <label key={field}>
                      <span className="mb-1 block text-xs text-[var(--brand-muted)]">
                        {t(`mes.${field === "completed_quantity" ? "completedQty" : field === "accepted_quantity" ? "acceptedQty" : "rejectedQty"}`)}
                      </span>
                      <input
                        type="number"
                        min="0"
                        max={line.allocated_quantity}
                        step="any"
                        disabled={!canEnterQty || isCompleted || busy}
                        value={
                          quantities[line.id]?.[field] ?? formatQty(line[field])
                        }
                        onChange={(e) => setQty(line.id, field, e.target.value)}
                        className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
                      />
                    </label>
                  ))}
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
                {t("mes.svarshikAccept")}
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
                {t("mes.svarshikStartWork")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.svarshikCompleteWork")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.svarshikStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
