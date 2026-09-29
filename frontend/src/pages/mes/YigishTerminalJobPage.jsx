import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import { useAuth } from "../../context/AuthContext";

function ProgressBar({ value, large = false }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));

  return (
    <div
      className={`w-full overflow-hidden rounded-full bg-gray-200 ${
        large ? "h-4" : "h-2.5"
      }`}
    >
      <div
        className="h-full rounded-full transition-all"
        style={{
          width: `${pct}%`,
          backgroundColor: "var(--brand-button)",
        }}
      />
    </div>
  );
}

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function formatDateTime(value) {
  if (!value) return "—";
  try {
    const raw = String(value);
    const normalized =
      /(?:Z|[+-]\\d{2}:?\\d{2})$/.test(raw)
        ? raw
        : raw.replace(" ", "T") + "Z";

    return new Date(normalized).toLocaleString("uz-UZ", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return "—";
  }
}

function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "—";

  const totalMinutes = Math.max(
    0,
    Math.round(Number(seconds) / 60)
  );

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0) {
    return minutes > 0
      ? `${hours} soat ${minutes} daqiqa`
      : `${hours} soat`;
  }

  return `${minutes} daqiqa`;
}

const QTY_FIELDS = [
  "completed_quantity",
  "accepted_quantity",
  "rejected_quantity",
];

export default function YigishTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();

  const canUse =
    isAdmin || hasPermission("mes_terminal_yigish");

  const [job, setJob] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [brigade, setBrigade] = useState(null);
  const [selectedWorkerIds, setSelectedWorkerIds] = useState([]);
  const [showWorkerModal, setShowWorkerModal] = useState(false);

  const load = useCallback(async () => {
    if (!canUse) return;

    setError("");

    try {
      const data = await api.mesYigishJob(id);
      setJob(data);

      const next = {};

      (data.yigish_parts || data.bom_lines || []).forEach((line) => {
        next[line.id] = {
          completed_quantity: formatQty(line.completed_quantity),
          accepted_quantity: formatQty(line.accepted_quantity),
          rejected_quantity: formatQty(line.rejected_quantity),
        };
      });

      setQuantities(next);
    } catch (e) {
      setError(e.message || "Yig‘ish topshirig‘ini yuklashda xatolik");
    } finally {
      setLoading(false);
    }
  }, [canUse, id]);

  useEffect(() => {
    load();
  }, [load]);

  const loadBrigade = useCallback(async () => {
    if (!canUse) return;

    try {
      const data = await api.mesYigishBrigade();
      setBrigade(data);
    } catch {
      setBrigade(null);
    }
  }, [canUse]);

  useEffect(() => {
    loadBrigade();
  }, [loadBrigade]);

  const stepState =
    job?.yigish_step?.state ||
    job?.step_state ||
    "pending_accept";

  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canEnterQty = stepState === "in_progress";

  const overallProgress = Number(
    job?.overall_progress_pct ??
      job?.yigish_progress_pct ??
      0
  );

  const canComplete =
    stepState === "in_progress" &&
    overallProgress >= 100 &&
    Boolean(brigade?.is_brigadier);

  const parts = job?.yigish_parts || job?.bom_lines || [];

  const submitCompletion = async () => {
    if (!selectedWorkerIds.length) {
      setMessage("Bajargan ishchini kamida bittasini tanlang.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const updated = await api.mesYigishCompleteJob(
        id,
        selectedWorkerIds
      );

      setJob(updated);
      setShowWorkerModal(false);
      setSelectedWorkerIds([]);
      setMessage("Yig‘ish topshirig‘i ishchilar bilan yakunlandi.");
      await loadBrigade();
    } catch (e) {
      setError(e.message || "Yig‘ishni yakunlashda xatolik");
    } finally {
      setBusy(false);
    }
  };

  const dirtyLines = useMemo(() => {
    return parts.filter((line) => {
      const draft = quantities[line.id] || {};

      return QTY_FIELDS.some(
        (field) =>
          formatQty(line[field]) !==
          (draft[field] ?? formatQty(line[field]))
      );
    });
  }, [parts, quantities]);

  const runAction = async (action) => {
    setBusy(true);
    setMessage("");

    try {
      let updated;

      if (action === "accept") {
        updated = await api.mesYigishAcceptJob(id);
      } else if (action === "start") {
        updated = await api.mesYigishStartJob(id);
      } else if (action === "complete") {
        setSelectedWorkerIds([]);
        setShowWorkerModal(true);
        return;
      }

      setJob(updated);
      await loadBrigade();

      if (action === "accept") {
        setMessage("Yig‘ish topshirig‘i qabul qilindi.");
      } else if (action === "start") {
        setMessage("Yig‘ish ishlari boshlandi.");
      } else {
        setMessage("Yig‘ish topshirig‘i tugallandi.");
      }
    } catch (e) {
      setMessage(e.message || "Amalni bajarishda xatolik");
    } finally {
      setBusy(false);
    }
  };

  const saveQuantities = async () => {
    if (!dirtyLines.length) return;

    setBusy(true);
    setMessage("");

    try {
      const lines = dirtyLines.map((line) => {
        const draft = quantities[line.id] || {};
        const payload = {
          bom_line_id: line.id,
        };

        QTY_FIELDS.forEach((field) => {
          const value =
            draft[field] ?? formatQty(line[field]);

          if (formatQty(line[field]) !== value) {
            payload[field] = Number(value);
          }
        });

        return payload;
      });

      const updated =
        await api.mesYigishUpdateQuantities(id, lines);

      setJob(updated);

      const next = {};

      (
        updated.yigish_parts ||
        updated.bom_lines ||
        []
      ).forEach((line) => {
        next[line.id] = {
          completed_quantity: formatQty(
            line.completed_quantity
          ),
          accepted_quantity: formatQty(
            line.accepted_quantity
          ),
          rejected_quantity: formatQty(
            line.rejected_quantity
          ),
        };
      });

      setQuantities(next);

      setMessage(
        updated.auto_completed
          ? "Miqdorlar saqlandi. Yig‘ish avtomatik tugallandi."
          : "Miqdorlar saqlandi."
      );
    } catch (e) {
      setMessage(
        e.message || "Miqdorlarni saqlashda xatolik"
      );
    } finally {
      setBusy(false);
    }
  };

  const setQty = (lineId, field, value) => {
    setQuantities((prev) => ({
      ...prev,
      [lineId]: {
        ...prev[lineId],
        [field]: value,
      },
    }));
  };

  if (!canUse) {
    return (
      <p className="py-12 text-center text-red-500">
        Yig‘ish terminaliga kirish huquqi yo‘q
      </p>
    );
  }

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!job) {
    return (
      <ErrorAlert
        message={
          error ||
          "Yig‘ish topshirig‘i topilmadi"
        }
      />
    );
  }

  return (
    <div className="pb-36">
      <BackButton
        fallback="/mes/terminal/yigish"
        label="Yig‘ish Terminali"
        className="mb-4"
      />

      {error ? (
        <div className="mb-4">
          <ErrorAlert message={error} />
        </div>
      ) : null}

      {message ? (
        <div className="mb-4 rounded-xl border bg-[var(--brand-card)] px-4 py-3 text-sm font-semibold">
          {message}
        </div>
      ) : null}

      {/* HEADER */}
      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">
              {job.job_number}
            </p>

            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>

            <p className="text-xs font-semibold text-blue-700">
              {job.yigish_step?.stage_name || "Yig‘ish"}
            </p>
          </div>

          <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-bold text-blue-900">
            {stepState === "pending_accept"
              ? "Kutilmoqda"
              : stepState === "accepted"
                ? "Qabul qilingan"
                : stepState === "in_progress"
                  ? "Jarayonda"
                  : stepState === "completed"
                    ? "Tugallangan"
                    : stepState}
          </span>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">
              Umumiy progress
            </span>

            <span className="font-black">
              {Math.round(overallProgress)}%
            </span>
          </div>

          <ProgressBar
            value={overallProgress}
            large
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border bg-gray-50 p-3">
            <p className="text-xs text-[var(--brand-muted)]">
              Boshlangan vaqt
            </p>
            <p className="mt-1 text-sm font-bold">
              {formatDateTime(job.yigish_step?.started_at)}
            </p>
          </div>

          <div className="rounded-xl border bg-gray-50 p-3">
            <p className="text-xs text-[var(--brand-muted)]">
              Tugagan vaqt
            </p>
            <p className="mt-1 text-sm font-bold">
              {formatDateTime(job.yigish_step?.completed_at)}
            </p>
          </div>

          <div className="rounded-xl border bg-blue-50 p-3">
            <p className="text-xs text-[var(--brand-muted)]">
              Amaldagi ishlash vaqti
            </p>
            <p className="mt-1 text-sm font-black text-blue-800">
              {job.yigish_step?.duration_seconds != null
                ? formatDuration(job.yigish_step.duration_seconds)
                : job.yigish_step?.started_at
                  ? "Jarayonda"
                  : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* PARTS */}
      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">
          Yig‘ish detallari
        </h3>

        {parts.length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">
            Detallar mavjud emas
          </p>
        ) : (
          <div className="space-y-4">
            {parts.map((line) => (
              <div
                key={line.id}
                className="rounded-xl border p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono font-bold">
                      {line.part_number}
                    </p>

                    <p className="text-sm">
                      {line.part_name}
                    </p>
                  </div>

                  <span className="text-sm font-bold">
                    {Math.round(
                      Number(line.progress_pct || 0)
                    )}
                    %
                  </span>
                </div>

                <div className="mt-2">
                  <ProgressBar
                    value={line.progress_pct}
                  />
                </div>

                <p className="mt-2 text-xs text-[var(--brand-muted)]">
                  Ajratilgan:{" "}
                  {formatQty(line.allocated_quantity)}{" "}
                  {line.unit || ""}
                </p>

                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {QTY_FIELDS.map((field) => {
                    const label =
                      field === "completed_quantity"
                        ? "Bajarilgan"
                        : field === "accepted_quantity"
                          ? "Qabul qilingan"
                          : "Brak";

                    return (
                      <label key={field}>
                        <span className="mb-1 block text-xs text-[var(--brand-muted)]">
                          {label}
                        </span>

                        <input
                          type="number"
                          min="0"
                          max={line.allocated_quantity}
                          step="any"
                          disabled={
                            !canEnterQty ||
                            isCompleted ||
                            busy
                          }
                          value={
                            quantities[line.id]?.[
                              field
                            ] ??
                            formatQty(line[field])
                          }
                          onChange={(e) =>
                            setQty(
                              line.id,
                              field,
                              e.target.value
                            )
                          }
                          className="w-full min-h-[48px] rounded-xl border px-3 text-lg font-bold"
                        />
                      </label>
                    );
                  })}
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
            style={{
              backgroundColor:
                "var(--brand-button)",
            }}
          >
            {busy
              ? "Saqlanmoqda..."
              : "Miqdorlarni saqlash"}
          </button>
        ) : null}
      </div>

      {/* ACTIONS */}
      {!isCompleted ? (
        <div className="fixed bottom-0 left-0 right-0 z-30 border-t bg-[var(--brand-card)] p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-lg md:static md:mt-4 md:rounded-2xl md:border md:p-4 md:shadow-none">
          <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row">
            {canAccept ? (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  runAction("accept")
                }
                className="min-h-[52px] flex-1 rounded-2xl text-base font-bold text-white disabled:opacity-60"
                style={{
                  backgroundColor:
                    "var(--brand-button)",
                }}
              >
                {busy
                  ? "Bajarilmoqda..."
                  : "Qabul qilish"}
              </button>
            ) : null}

            {canStart ? (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  runAction("start")
                }
                className="min-h-[52px] flex-1 rounded-2xl text-base font-bold text-white disabled:opacity-60"
                style={{
                  backgroundColor:
                    "var(--brand-button)",
                }}
              >
                {busy
                  ? "Bajarilmoqda..."
                  : "Yig‘ishni boshlash"}
              </button>
            ) : null}

            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setSelectedWorkerIds([]);
                  setMessage("");
                  setShowWorkerModal(true);
                }}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {busy
                  ? "Bajarilmoqda..."
                  : "Yig‘ishni tugatish"}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* BRIGADE */}
      {brigade ? (
        <div className="mb-28 mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 md:mb-0">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand-muted)]">
                Yig‘ish brigadasi
              </div>
              <div className="mt-1 text-lg font-black">
                {brigade.name || "—"}
              </div>
            </div>

            <div className="text-sm">
              <span className="font-semibold">Brigadir:</span>{" "}
              {brigade.brigadier?.full_name ||
                brigade.brigadier?.username ||
                "—"}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {(brigade.members || []).map((worker) => (
              <span
                key={worker.id}
                className="rounded-full bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-800"
              >
                {worker.full_name || worker.username}
              </span>
            ))}

            {!brigade.members?.length ? (
              <span className="text-sm text-[var(--brand-muted)]">
                Brigadaga ishchilar biriktirilmagan.
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* WORKER SELECTION MODAL */}
      {showWorkerModal ? (
        <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 p-3 sm:items-center">
          <div className="w-full max-w-lg rounded-3xl bg-[var(--brand-card)] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-black">
                  Bajargan ishchilar
                </h3>
                <p className="mt-1 text-sm text-[var(--brand-muted)]">
                  Shu Yig‘ish topshirig‘ida amalda ishlagan ishchilarni tanlang.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (!busy) setShowWorkerModal(false);
                }}
                className="rounded-xl px-3 py-2 text-sm font-bold text-gray-500 hover:bg-gray-100"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-2">
              {(brigade?.members || []).map((worker) => {
                const checked = selectedWorkerIds.includes(worker.id);

                return (
                  <label
                    key={worker.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-2xl border p-3 transition ${
                      checked
                        ? "border-[var(--brand-button)] bg-blue-50"
                        : "border-gray-200"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={busy}
                      onChange={(event) => {
                        setSelectedWorkerIds((current) =>
                          event.target.checked
                            ? [...current, worker.id]
                            : current.filter((idValue) => idValue !== worker.id)
                        );
                      }}
                      className="h-5 w-5"
                    />

                    <div className="min-w-0">
                      <div className="font-bold">
                        {worker.full_name || worker.username}
                      </div>
                      <div className="text-xs text-[var(--brand-muted)]">
                        {[worker.employee_id, worker.position]
                          .filter(Boolean)
                          .join(" · ") || worker.username}
                      </div>
                    </div>
                  </label>
                );
              })}

              {!brigade?.members?.length ? (
                <div className="rounded-2xl bg-gray-50 p-4 text-sm text-gray-600">
                  Avval Admin → MES → Brigadalar bo‘limida ishchilarni brigadaga biriktiring.
                </div>
              ) : null}
            </div>

            <div className="mt-5 flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => setShowWorkerModal(false)}
                className="min-h-[50px] flex-1 rounded-2xl border text-sm font-bold"
              >
                Bekor qilish
              </button>

              <button
                type="button"
                disabled={busy || !selectedWorkerIds.length}
                onClick={submitCompletion}
                className="min-h-[50px] flex-1 rounded-2xl bg-green-600 px-4 text-sm font-bold text-white disabled:opacity-50"
              >
                {busy
                  ? "Saqlanmoqda..."
                  : `Bajardim (${selectedWorkerIds.length})`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
