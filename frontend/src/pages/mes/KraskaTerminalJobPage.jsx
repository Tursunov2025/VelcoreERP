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

const QTY_FIELDS = ["painted_quantity", "accepted_quantity", "rejected_quantity"];

export default function KraskaTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_kraska");

  const [job, setJob] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [paintMeta, setPaintMeta] = useState({
    color_name: "",
    ral_code: "",
    paint_type: "",
    batch_number: "",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const data = await api.mesKraskaJob(id);
      setJob(data);
      const next = {};
      (data.paint_parts || []).forEach((line) => {
        next[line.id] = {
          painted_quantity: formatQty(line.painted_quantity),
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
        };
      });
      setQuantities(next);
      setPaintMeta(data.paint_metadata || paintMeta);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canUse, id]);

  useEffect(() => {
    load();
  }, [load]);

  const stepState = job?.paint_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterQty = stepState === "in_progress";
  const canSendDrying =
    stepState === "in_progress" && Number(job?.overall_progress_pct || 0) >= 100;
  const canComplete = stepState === "drying";

  const dirtyLines = useMemo(() => {
    if (!job?.paint_parts) return [];
    return job.paint_parts.filter((line) => {
      const draft = quantities[line.id] || {};
      return QTY_FIELDS.some(
        (field) => formatQty(line[field]) !== (draft[field] ?? formatQty(line[field]))
      );
    });
  }, [job, quantities]);

  const paintMetaDirty = useMemo(() => {
    if (!job?.paint_metadata) return false;
    return Object.keys(paintMeta).some((k) => (paintMeta[k] || "") !== (job.paint_metadata[k] || ""));
  }, [job, paintMeta]);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesKraskaAcceptJob(id);
      else if (action === "start") updated = await api.mesKraskaStartJob(id);
      else if (action === "drying") updated = await api.mesKraskaSendToDrying(id);
      else if (action === "complete") updated = await api.mesKraskaCompleteJob(id);
      setJob(updated);
      setToast(t(`mes.kraskaAction_${action}`));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const savePaintMeta = async () => {
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesKraskaUpdatePaintMetadata(id, paintMeta);
      setJob(updated);
      setPaintMeta(updated.paint_metadata);
      setToast(t("mes.kraskaPaintSaved"));
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
          if (formatQty(line[field]) !== val) payload[field] = Number(val);
        });
        return payload;
      });
      const updated = await api.mesKraskaUpdateQuantities(id, lines);
      setJob(updated);
      setToast(updated.auto_completed ? t("mes.kraskaAutoCompleted") : t("mes.kraskaQtySaved"));
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
    <div className="pb-40">
      <Link
        to="/mes/terminal/kraska"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.kraskaTerminal")}
      </Link>

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.paint_step?.stage_name}
            </p>
          </div>
          <span className="rounded-full bg-purple-100 px-3 py-1 text-sm font-bold text-purple-900">
            {t(`mes.kraskaStep_${stepState}`)}
          </span>
        </div>
        <div className="mt-4">
          <div className="mb-2 flex justify-between text-sm">
            <span className="font-semibold">{t("mes.overallProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-3 text-lg font-bold">{t("mes.paintMetadata")}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            ["color_name", t("mes.paintColor")],
            ["ral_code", t("mes.paintRal")],
            ["paint_type", t("mes.paintType")],
            ["batch_number", t("mes.paintBatch")],
          ].map(([key, label]) => (
            <label key={key} className="block text-sm">
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{label}</span>
              <input
                type="text"
                disabled={isCompleted || busy}
                value={paintMeta[key] || ""}
                onChange={(e) => setPaintMeta((prev) => ({ ...prev, [key]: e.target.value }))}
                className="w-full min-h-[44px] rounded-xl border px-3"
              />
            </label>
          ))}
        </div>
        {paintMetaDirty && !isCompleted ? (
          <button
            type="button"
            disabled={busy}
            onClick={savePaintMeta}
            className="mt-3 w-full min-h-[44px] rounded-xl border text-sm font-semibold"
          >
            {t("mes.savePaintMetadata")}
          </button>
        ) : null}
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.paintParts")}</h3>
        <div className="space-y-4">
          {(job.paint_parts || []).map((line) => (
            <div key={line.id} className="rounded-xl border p-4">
              <div className="flex justify-between gap-2">
                <div>
                  <p className="font-mono font-bold">{line.part_number}</p>
                  <p className="text-sm">{line.part_name}</p>
                </div>
                <span className="text-sm font-bold">{Math.round(line.progress_pct || 0)}%</span>
              </div>
              <ProgressBar value={line.progress_pct} />
              <p className="mt-2 text-xs text-[var(--brand-muted)]">
                / {formatQty(line.allocated_quantity)} {line.unit}
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {[
                  ["painted_quantity", t("mes.paintedQty")],
                  ["accepted_quantity", t("mes.acceptedQty")],
                  ["rejected_quantity", t("mes.rejectedQty")],
                ].map(([field, label]) => (
                  <label key={field}>
                    <span className="mb-1 block text-xs text-[var(--brand-muted)]">{label}</span>
                    <input
                      type="number"
                      min="0"
                      max={line.allocated_quantity}
                      step="any"
                      disabled={!canEnterQty || isCompleted || busy}
                      value={quantities[line.id]?.[field] ?? formatQty(line[field])}
                      onChange={(e) =>
                        setQuantities((prev) => ({
                          ...prev,
                          [line.id]: { ...prev[line.id], [field]: e.target.value },
                        }))
                      }
                      className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        {canEnterQty && dirtyLines.length > 0 ? (
          <button
            type="button"
            disabled={busy}
            onClick={saveQuantities}
            className="mt-4 w-full min-h-[52px] rounded-2xl text-base font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {busy ? t("common.saving") : t("mes.saveQuantities")}
          </button>
        ) : null}
      </div>

      {!isCompleted ? (
        <div className="fixed bottom-0 left-0 right-0 z-30 border-t bg-[var(--brand-card)] p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-lg">
          <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row sm:flex-wrap">
            {canAccept ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("accept")}
                className="min-h-[52px] flex-1 rounded-2xl text-base font-bold text-white disabled:opacity-60"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("mes.kraskaAccept")}
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
                {t("mes.kraskaStartWork")}
              </button>
            ) : null}
            {canSendDrying ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("drying")}
                className="min-h-[52px] flex-1 rounded-2xl bg-purple-600 text-base font-bold text-white disabled:opacity-60"
              >
                {t("mes.kraskaSendDrying")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.kraskaCompleteWork")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.kraskaStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
