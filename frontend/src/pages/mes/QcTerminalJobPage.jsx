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

const QTY_FIELDS = ["accepted_quantity", "rejected_quantity", "rework_quantity"];

export default function QcTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canUse = isAdmin || hasPermission("mes_terminal_qc");

  const [job, setJob] = useState(null);
  const [reasons, setReasons] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [reworkForm, setReworkForm] = useState({ bom_line_id: "", quantity: "", rejection_reason_id: "", notes: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const [data, reasonsData] = await Promise.all([
        api.mesQcJob(id),
        api.mesQcRejectionReasons(),
      ]);
      setJob(data);
      setReasons(reasonsData.reasons || []);
      const next = {};
      (data.qc_parts || data.bom_lines || []).forEach((line) => {
        next[line.id] = {
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
          rework_quantity: formatQty(line.rework_quantity),
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

  const stepState = job?.qc_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterQty = stepState === "in_progress";
  const canComplete =
    stepState === "in_progress" &&
    Number(job?.overall_progress_pct || 0) >= 100 &&
    !(job?.open_rework_count > 0);

  const dirtyLines = useMemo(() => {
    if (!job?.qc_parts) return [];
    return job.qc_parts.filter((line) => {
      const draft = quantities[line.id] || {};
      return QTY_FIELDS.some(
        (field) => formatQty(line[field]) !== (draft[field] ?? formatQty(line[field]))
      );
    });
  }, [job, quantities]);

  const openRework = (job?.rework_records || []).filter(
    (r) => r.status === "pending" || r.status === "in_progress"
  );

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesQcAcceptJob(id);
      else if (action === "start") updated = await api.mesQcStartJob(id);
      else if (action === "complete") updated = await api.mesQcCompleteJob(id);
      setJob(updated);
      setToast(t(`mes.qcAction_${action}`));
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
      const updated = await api.mesQcUpdateQuantities(id, lines);
      setJob(updated);
      const next = {};
      (updated.qc_parts || []).forEach((line) => {
        next[line.id] = {
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
          rework_quantity: formatQty(line.rework_quantity),
        };
      });
      setQuantities(next);
      setToast(updated.auto_completed ? t("mes.qcAutoCompleted") : t("mes.qcQtySaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const createRework = async () => {
    const bomLineId = Number(reworkForm.bom_line_id);
    const qty = Number(reworkForm.quantity);
    if (!bomLineId || !qty || qty <= 0) {
      setToast(t("mes.qcReworkFormInvalid"));
      return;
    }
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesQcCreateRework(id, {
        bom_line_id: bomLineId,
        quantity: qty,
        rejection_reason_id: reworkForm.rejection_reason_id
          ? Number(reworkForm.rejection_reason_id)
          : null,
        notes: reworkForm.notes,
      });
      setJob(updated);
      setReworkForm({ bom_line_id: "", quantity: "", rejection_reason_id: "", notes: "" });
      setToast(t("mes.qcReworkCreated"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const runReworkAction = async (reworkId, action) => {
    setBusy(true);
    setToast("");
    try {
      if (action === "start") await api.mesQcStartRework(reworkId);
      else await api.mesQcCompleteRework(reworkId);
      await load();
      setToast(t(`mes.qcReworkAction_${action}`));
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
      <BackButton fallback="/mes/terminal/qc" label={t("mes.qcTerminal")} className="mb-4" />

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>
            <p className="text-xs font-semibold text-blue-700">{job.qc_step?.stage_name}</p>
          </div>
          <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-bold text-blue-900">
            {t(`mes.terminalStep_${stepState}`)}
          </span>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.overallProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
          <p className="mt-1 text-xs text-[var(--brand-muted)]">{t("mes.qcProgressHint")}</p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.qcParts")}</h3>

        {(job.qc_parts || []).length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.noSnapshotYet")}</p>
        ) : (
          <div className="space-y-4">
            {(job.qc_parts || []).map((line) => (
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
                        {t(
                          `mes.${
                            field === "accepted_quantity"
                              ? "acceptedQty"
                              : field === "rejected_quantity"
                                ? "rejectedQty"
                                : "reworkQty"
                          }`
                        )}
                      </span>
                      <input
                        type="number"
                        min="0"
                        max={line.allocated_quantity}
                        step="any"
                        disabled={!canEnterQty || isCompleted || busy}
                        value={quantities[line.id]?.[field] ?? formatQty(line[field])}
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

      {canEnterQty ? (
        <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
          <h3 className="mb-4 text-lg font-bold">{t("mes.qcCreateRework")}</h3>
          <div className="grid gap-3">
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.qcSelectPart")}</span>
              <select
                value={reworkForm.bom_line_id}
                onChange={(e) => setReworkForm((f) => ({ ...f, bom_line_id: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3"
                disabled={busy}
              >
                <option value="">{t("mes.qcSelectPart")}</option>
                {(job.qc_parts || []).map((line) => (
                  <option key={line.id} value={line.id}>
                    {line.part_number} — {line.part_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.reworkQty")}</span>
              <input
                type="number"
                min="0"
                step="any"
                value={reworkForm.quantity}
                onChange={(e) => setReworkForm((f) => ({ ...f, quantity: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
                disabled={busy}
              />
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.qcRejectionReason")}</span>
              <select
                value={reworkForm.rejection_reason_id}
                onChange={(e) => setReworkForm((f) => ({ ...f, rejection_reason_id: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3"
                disabled={busy}
              >
                <option value="">{t("mes.qcNoReason")}</option>
                {reasons.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("common.notes")}</span>
              <textarea
                value={reworkForm.notes}
                onChange={(e) => setReworkForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
                className="w-full rounded-xl border px-3 py-2"
                disabled={busy}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={createRework}
              className="min-h-[52px] rounded-2xl border-2 border-orange-500 text-base font-bold text-orange-700 disabled:opacity-60"
            >
              {t("mes.qcCreateReworkBtn")}
            </button>
          </div>
        </div>
      ) : null}

      {(job.rework_records || []).length > 0 ? (
        <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
          <h3 className="mb-4 text-lg font-bold">{t("mes.qcReworkRecords")}</h3>
          <div className="space-y-3">
            {(job.rework_records || []).map((record) => (
              <div key={record.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono font-bold">{record.part_number}</p>
                    <p className="text-sm">{record.rejection_reason_name || t("mes.qcNoReason")}</p>
                    <p className="text-sm font-bold">
                      {t("mes.reworkQty")}: {formatQty(record.quantity)}
                    </p>
                  </div>
                  <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-bold text-orange-900">
                    {t(`mes.qcReworkStatus_${record.status}`)}
                  </span>
                </div>
                {record.status === "pending" || record.status === "in_progress" ? (
                  <div className="mt-3 flex gap-2">
                    {record.status === "pending" ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => runReworkAction(record.id, "start")}
                        className="min-h-[44px] flex-1 rounded-xl text-sm font-bold text-white disabled:opacity-60"
                        style={{ backgroundColor: "var(--brand-button)" }}
                      >
                        {t("mes.qcReworkStart")}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => runReworkAction(record.id, "complete")}
                      className="min-h-[44px] flex-1 rounded-xl border-2 border-green-600 text-sm font-bold text-green-700 disabled:opacity-60"
                    >
                      {t("mes.qcReworkComplete")}
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {openRework.length > 0 && canComplete === false && stepState === "in_progress" ? (
        <p className="mt-4 rounded-2xl border border-orange-200 bg-orange-50 p-4 text-center text-sm font-semibold text-orange-800">
          {t("mes.qcCompleteBlockedRework")}
        </p>
      ) : null}

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
                {t("mes.qcAccept")}
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
                {t("mes.qcStartInspection")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.qcCompleteInspection")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.qcStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
