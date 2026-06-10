import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import { useFeatureFlags } from "../../hooks/useFeatureFlags";
import { parseLabelCode } from "../../utils/labelCode";

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

export default function DispatchTerminalJobPage() {
  const { id } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const { traceabilityEnabled } = useFeatureFlags();
  const canUse = isAdmin || hasPermission("mes_terminal_dispatch");

  const [job, setJob] = useState(null);
  const [transport, setTransport] = useState({
    vehicle_number: "",
    driver_name: "",
    driver_phone: "",
    transport_company: "",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [scanCode, setScanCode] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    setError("");
    try {
      const data = await api.mesDispatchJob(id);
      setJob(data);
      const d = data.dispatch || {};
      setTransport({
        vehicle_number: d.vehicle_number || "",
        driver_name: d.driver_name || "",
        driver_phone: d.driver_phone || "",
        transport_company: d.transport_company || "",
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

  const dispatch = job?.dispatch;
  const dispatchStatus = dispatch?.status;
  const stepState = job?.dispatch_step?.state || job?.step_state || "pending_accept";
  const isDone = dispatchStatus === "delivered" || job?.status === "completed";

  const canAccept = !dispatch && stepState === "pending_accept";
  const canStart = dispatch?.status === "pending" && stepState === "accepted";
  const canLoad = dispatch?.status === "loading";
  const canShip =
    dispatch?.status === "loading" &&
    (dispatch?.packages || []).length > 0 &&
    (dispatch?.packages || []).every((p) => p.status !== "pending");
  const canDeliver = dispatch?.status === "shipped";

  const transportDirty = useMemo(() => {
    if (!dispatch) return false;
    return (
      transport.vehicle_number !== (dispatch.vehicle_number || "") ||
      transport.driver_name !== (dispatch.driver_name || "") ||
      transport.driver_phone !== (dispatch.driver_phone || "") ||
      transport.transport_company !== (dispatch.transport_company || "")
    );
  }, [dispatch, transport]);

  const runAction = async (action) => {
    setBusy(true);
    setToast("");
    try {
      let updated;
      if (action === "accept") updated = await api.mesDispatchAccept(id);
      else if (action === "start") updated = await api.mesDispatchStartLoading(id);
      else if (action === "ship") updated = await api.mesDispatchShip(id);
      else if (action === "deliver") updated = await api.mesDispatchDeliver(id);
      setJob(updated);
      setToast(t(`mes.dispatchAction_${action}`));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveTransport = async () => {
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesDispatchUpdateTransport(id, transport);
      setJob(updated);
      setToast(t("mes.dispatchTransportSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const scanLoad = async () => {
    const code = parseLabelCode(scanCode);
    if (!code) {
      setToast(t("mes.dispatchScanPlaceholder"));
      return;
    }
    setBusy(true);
    setToast("");
    try {
      await api.mesDispatchScanLabel(id, code);
      await load();
      setScanCode("");
      setToast(t("mes.dispatchPackageLoaded"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const loadPackage = async (packageId) => {
    setBusy(true);
    setToast("");
    try {
      const updated = await api.mesDispatchLoadPackage(id, packageId);
      setJob(updated);
      setToast(t("mes.dispatchPackageLoaded"));
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
      <BackButton fallback="/mes/terminal/dispatch" label={t("mes.dispatchTerminal")} className="mb-4" />

      <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-2xl font-black">{job.job_number}</p>
            {dispatch?.dispatch_number ? (
              <p className="font-mono text-sm font-bold text-teal-700">{dispatch.dispatch_number}</p>
            ) : null}
            <p className="text-sm text-[var(--brand-muted)]">
              {job.template_code} · {job.customer_name || job.template_name}
            </p>
          </div>
          <span className="rounded-full bg-teal-100 px-3 py-1 text-sm font-bold text-teal-900">
            {dispatch?.status
              ? t(`mes.dispatchStatus_${dispatch.status}`)
              : t(`mes.terminalStep_${stepState}`)}
          </span>
        </div>

        {dispatch ? (
          <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <p>
              <span className="text-[var(--brand-muted)]">{t("mes.dispatchCustomer")}: </span>
              <span className="font-semibold">{dispatch.customer_name || "—"}</span>
            </p>
            <p>
              <span className="text-[var(--brand-muted)]">{t("mes.packageCount")}: </span>
              <span className="font-semibold">{dispatch.package_count}</span>
            </p>
            {dispatch.ship_date ? (
              <p>
                <span className="text-[var(--brand-muted)]">{t("mes.shipDate")}: </span>
                <span className="font-semibold">{new Date(dispatch.ship_date).toLocaleString()}</span>
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold">{t("mes.loadingProgress")}</span>
            <span className="font-black">{Math.round(job.overall_progress_pct || 0)}%</span>
          </div>
          <ProgressBar value={job.overall_progress_pct} large />
        </div>
      </div>

      {dispatch ? (
        <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
          <h3 className="mb-4 text-lg font-bold">{t("mes.transportInfo")}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.vehicleNumber")}</span>
              <input
                type="text"
                disabled={isDone || busy || dispatchStatus === "shipped" || dispatchStatus === "delivered"}
                value={transport.vehicle_number}
                onChange={(e) => setTransport((f) => ({ ...f, vehicle_number: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3 font-semibold uppercase"
              />
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.driverName")}</span>
              <input
                type="text"
                disabled={isDone || busy}
                value={transport.driver_name}
                onChange={(e) => setTransport((f) => ({ ...f, driver_name: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3"
              />
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.driverPhone")}</span>
              <input
                type="tel"
                disabled={isDone || busy}
                value={transport.driver_phone}
                onChange={(e) => setTransport((f) => ({ ...f, driver_phone: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3"
              />
            </label>
            <label>
              <span className="mb-1 block text-xs text-[var(--brand-muted)]">{t("mes.transportCompany")}</span>
              <input
                type="text"
                disabled={isDone || busy}
                value={transport.transport_company}
                onChange={(e) => setTransport((f) => ({ ...f, transport_company: e.target.value }))}
                className="w-full min-h-[48px] rounded-xl border px-3"
              />
            </label>
          </div>
          {transportDirty && !isDone ? (
            <button
              type="button"
              disabled={busy}
              onClick={saveTransport}
              className="mt-4 w-full min-h-[48px] rounded-2xl text-sm font-bold text-white disabled:opacity-60"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {t("mes.saveTransportInfo")}
            </button>
          ) : null}
        </div>
      ) : null}

      {canLoad && traceabilityEnabled ? (
        <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4">
          <h3 className="mb-2 text-lg font-bold">{t("mes.dispatchScanQr")}</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={scanCode}
              onChange={(e) => setScanCode(e.target.value)}
              placeholder={t("mes.dispatchScanPlaceholder")}
              className="min-h-[48px] flex-1 rounded-xl border px-3 font-mono text-sm"
            />
            <button
              type="button"
              disabled={busy}
              onClick={scanLoad}
              className="min-h-[48px] rounded-xl px-4 text-sm font-bold text-white disabled:opacity-60"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {t("mes.dispatchScanLoad")}
            </button>
          </div>
        </div>
      ) : null}

      {dispatch?.packages?.length ? (
        <div className="mt-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
          <h3 className="mb-4 text-lg font-bold">{t("mes.dispatchPackages")}</h3>
          <div className="space-y-3">
            {dispatch.packages.map((pkg) => (
              <div key={pkg.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono font-bold">{pkg.label_code || pkg.package_number}</p>
                    <p className="text-xs text-[var(--brand-muted)]">
                      {pkg.location_code || "—"} · {pkg.net_weight_kg}/{pkg.gross_weight_kg} kg
                    </p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold">
                    {t(`mes.dispatchPkgStatus_${pkg.status}`)}
                  </span>
                </div>
                {canLoad && pkg.status === "pending" ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => loadPackage(pkg.package_id)}
                    className="mt-3 w-full min-h-[48px] rounded-xl text-sm font-bold text-white disabled:opacity-60"
                    style={{ backgroundColor: "var(--brand-button)" }}
                  >
                    {t("mes.loadPackage")}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!isDone ? (
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
                {t("mes.dispatchAccept")}
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
                {t("mes.dispatchStartLoading")}
              </button>
            ) : null}
            {canShip ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("ship")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-blue-600 text-base font-bold text-blue-700 disabled:opacity-60"
              >
                {t("mes.dispatchShip")}
              </button>
            ) : null}
            {canDeliver ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => runAction("deliver")}
                className="min-h-[52px] flex-1 rounded-2xl border-2 border-green-600 text-base font-bold text-green-700 disabled:opacity-60"
              >
                {t("mes.dispatchDeliver")}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-2xl border border-green-200 bg-green-50 p-4 text-center font-semibold text-green-800">
          {t("mes.dispatchLifecycleComplete")}
        </p>
      )}

      {error ? <ErrorAlert message={error} className="mt-4" /> : null}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
