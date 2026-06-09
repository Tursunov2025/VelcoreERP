import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import { useFeatureFlags } from "../../hooks/useFeatureFlags";

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

export default function WarehouseTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const { traceabilityEnabled } = useFeatureFlags();
  const canUse = isAdmin || hasPermission("mes_terminal_warehouse");

  const [job, setJob] = useState(null);
  const [locations, setLocations] = useState([]);
  const [selections, setSelections] = useState({});
  const [zoneFields, setZoneFields] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const [data, locData] = await Promise.all([
        api.mesWarehouseJob(id),
        api.mesWarehouseLocations(),
      ]);
      setJob(data);
      setLocations(locData.locations || []);
      const next = {};
      const zones = {};
      (data.packages || []).forEach((pkg) => {
        next[pkg.id] = pkg.location_id ? String(pkg.location_id) : "";
        zones[pkg.id] = {
          warehouse_zone: pkg.warehouse_zone || "",
          rack: pkg.rack || "",
          shelf: pkg.shelf || "",
        };
      });
      setSelections(next);
      setZoneFields(zones);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canUse, id]);

  useEffect(() => {
    load();
  }, [load]);

  const stepState = job?.warehouse_step?.state || job?.step_state || "pending_accept";
  const isCompleted = stepState === "completed";
  const canAccept = stepState === "pending_accept";
  const canStart = stepState === "accepted";
  const canPlace = stepState === "in_progress";
  const canComplete =
    stepState === "in_progress" &&
    Number(job?.package_total || 0) > 0 &&
    Number(job?.packages_placed || 0) >= Number(job?.package_total || 0);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesWarehouseAcceptReceipt(id);
      else if (action === "start") updated = await api.mesWarehouseStartPlacement(id);
      else if (action === "complete") updated = await api.mesWarehouseCompleteReceipt(id);
      setJob(updated);
      setToast(t(`mes.warehouseAction_${action}`));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveTraceLocation = async (pkg) => {
    if (!pkg.label_code) {
      setToast(t("mes.traceLabel"));
      return;
    }
    const fields = zoneFields[pkg.id] || {};
    setBusy(true);
    try {
      await api.packageAssignLocation(pkg.label_code, {
        warehouse_zone: fields.warehouse_zone || "",
        rack: fields.rack || "",
        shelf: fields.shelf || "",
      });
      setToast(t("controlCenter.saved"));
      await load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const placePackage = async (packageId) => {
    const locationId = Number(selections[packageId]);
    if (!locationId) {
      setToast(t("mes.warehouseSelectLocation"));
      return;
    }
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesWarehousePlacePackage(id, packageId, locationId);
      setJob(updated);
      setToast(t("mes.warehousePackagePlaced"));
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
        to="/mes/terminal/warehouse"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.warehouseTerminal")}
      </Link>

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.template_name}
            </p>
            <p className="text-xs font-semibold text-indigo-700">{job.warehouse_step?.stage_name}</p>
          </div>
          <span className="rounded-full bg-indigo-100 px-3 py-1 text-sm font-bold text-indigo-900">
            {t(`mes.terminalStep_${stepState}`)}
          </span>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.placementProgress")}</span>
            <span className="font-black">
              {job.packages_placed}/{job.package_total} · {Math.round(job.overall_progress_pct || 0)}%
            </span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
        </div>
      </div>

      <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <h3 className="mb-4 text-lg font-bold">{t("mes.packagesToPlace")}</h3>

        {(job.packages || []).length === 0 ? (
          <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.noPackagesYet")}</p>
        ) : (
          <div className="space-y-3">
            {(job.packages || []).map((pkg) => (
              <div key={pkg.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-mono font-bold">{pkg.label_code || pkg.package_number}</p>
                  {pkg.location_code ? (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-bold text-green-800">
                      {pkg.location_code}
                    </span>
                  ) : (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-700">
                      {t("mes.notPlaced")}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-[var(--brand-muted)]">
                  {pkg.package_type || "—"} · {pkg.net_weight_kg} / {pkg.gross_weight_kg} kg
                </p>

                {canPlace && !pkg.location_id ? (
                  <div className="mt-3 flex gap-2">
                    <select
                      value={selections[pkg.id] || ""}
                      onChange={(e) =>
                        setSelections((prev) => ({ ...prev, [pkg.id]: e.target.value }))
                      }
                      className="min-h-[48px] flex-1 rounded-xl border px-3"
                      disabled={busy}
                    >
                      <option value="">{t("mes.warehouseSelectLocation")}</option>
                      {locations.map((loc) => (
                        <option key={loc.id} value={loc.id}>
                          {loc.code}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => placePackage(pkg.id)}
                      className="min-h-[48px] rounded-xl px-4 text-sm font-bold text-white disabled:opacity-60"
                      style={{ backgroundColor: "var(--brand-button)" }}
                    >
                      {t("mes.placePackage")}
                    </button>
                  </div>
                ) : null}
                {traceabilityEnabled && pkg.label_code ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <input
                      placeholder={t("mes.traceZone")}
                      className="rounded-xl border px-3 py-2 text-sm"
                      value={zoneFields[pkg.id]?.warehouse_zone || ""}
                      onChange={(e) =>
                        setZoneFields((prev) => ({
                          ...prev,
                          [pkg.id]: { ...prev[pkg.id], warehouse_zone: e.target.value },
                        }))
                      }
                    />
                    <input
                      placeholder={t("mes.traceRack")}
                      className="rounded-xl border px-3 py-2 text-sm"
                      value={zoneFields[pkg.id]?.rack || ""}
                      onChange={(e) =>
                        setZoneFields((prev) => ({
                          ...prev,
                          [pkg.id]: { ...prev[pkg.id], rack: e.target.value },
                        }))
                      }
                    />
                    <input
                      placeholder={t("mes.traceShelf")}
                      className="rounded-xl border px-3 py-2 text-sm"
                      value={zoneFields[pkg.id]?.shelf || ""}
                      onChange={(e) =>
                        setZoneFields((prev) => ({
                          ...prev,
                          [pkg.id]: { ...prev[pkg.id], shelf: e.target.value },
                        }))
                      }
                    />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => saveTraceLocation(pkg)}
                      className="sm:col-span-3 min-h-[44px] rounded-xl border-2 border-indigo-600 text-sm font-bold text-indigo-700"
                    >
                      {t("mes.traceSaveLocation")}
                    </button>
                  </div>
                ) : null}
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
                {t("mes.warehouseAcceptReceipt")}
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
                {t("mes.warehouseStartPlacement")}
              </button>
            ) : null}
            {canComplete ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("complete")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.warehouseCompleteReceipt")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.warehouseStageDone")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
