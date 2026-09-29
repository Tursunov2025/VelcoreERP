import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import LogisticsSectionNav from "../../components/logistics/LogisticsSectionNav";
import ProductPassportActions from "../../components/traceability/ProductPassportActions";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import { useLocale } from "../../context/LocaleContext";
import {
  apiMessage,
  date,
  idempotency,
  number,
  panel,
} from "../productionProjects/projectUi";

const statuses = [
  "",
  "draft",
  "planned",
  "loading",
  "loaded",
  "dispatched",
  "in_transit",
  "delivered",
  "accepted",
  "cancelled",
];
const loadingViews = ["planned", "today", "active", "completed"];
export default function CanonicalShipmentsPage({ loadingOnly = false }) {
  const { t, locale } = useLocale();
  const [params, setParams] = useSearchParams();
  const keys = useRef({});
  const createTripKey = useRef(null);
  const [rows, setRows] = useState([]),
    [busy, setBusy] = useState(true),
    [action, setAction] = useState(""),
    [error, setError] = useState("");
  const [vehicles, setVehicles] = useState([]),
    [projects, setProjects] = useState([]),
    [drivers, setDrivers] = useState([]),
    [ready, setReady] = useState({ items: [], projects: [], totals: {} }),
    [selected, setSelected] = useState([]),
    [showCreate, setShowCreate] = useState(false);
  const [targetTripId, setTargetTripId] = useState("");
  const [trip, setTrip] = useState({
    trip_number: "",
    project_id: "",
    vehicle_id: "",
    driver_user_id: "",
    planned_loading_at: "",
    planned_departure_at: "",
    delivery_deadline_at: "",
    evidence_policy: "required",
    completeness_required: true,
    notes: "",
  });
  const filter =
    params.get(loadingOnly ? "view" : "status") ||
    (loadingOnly ? "planned" : "");
  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [r, v, p, d, cargo] = await Promise.all([
        api.finishedTrips(),
        api.finishedVehicles(true),
        api.productionProjects({ page_size: 100 }),
        api.finishedDrivers(),
        api.finishedReadyCargo(),
      ]);
      const vm = new Map((v.vehicles || []).map((x) => [x.id, x])),
        pm = new Map((p.items || []).map((x) => [x.id, x]));
      const enriched = await Promise.all(
        (r.trips || []).map(async (x) => ({
          ...x,
          vehicle: vm.get(x.vehicle_id),
          project: pm.get(x.project_id),
          progress: await api.finishedTripProgress(x.id),
          plan: await api.finishedLoadingPlan(x.id),
        }))
      );
      setRows(enriched);
      setVehicles(v.vehicles || []);
      setProjects(p.items || []);
      setDrivers(d.drivers || []);
      setReady(cargo);
      setSelected((current) => {
        const requested = Number(params.get("placement_id"));
        if (requested && (cargo.items || []).some((x) => x.id === requested)) return [requested];
        return current.filter((id) => (cargo.items || []).some((x) => x.id === id));
      });
      setError("");
    } catch (e) {
      setError(apiMessage(e, t));
    } finally {
      setBusy(false);
    }
  }, [t, params]);
  useEffect(() => {
    load();
  }, [load]);
  const visible = useMemo(
    () =>
      rows.filter((x) => {
        if (!loadingOnly) return !filter || x.status === filter;
        const planned = x.planned_departure_at
            ? new Date(x.planned_departure_at)
            : null,
          today =
            planned && planned.toDateString() === new Date().toDateString();
        if (filter === "planned")
          return ["draft", "planned"].includes(x.status);
        if (filter === "today")
          return (
            today && !["delivered", "accepted", "cancelled"].includes(x.status)
          );
        if (filter === "active") return x.status === "loading";
        return [
          "loaded",
          "dispatched",
          "in_transit",
          "delivered",
          "accepted",
        ].includes(x.status);
      }),
    [rows, filter, loadingOnly]
  );
  const run = async (x, type) => {
    setAction(`${x.id}-${type}`);
    try {
      if (type === "start")
        await api.finishedTripTransition(x.id, {
          status: "loading",
          expected_version: x.version,
        });
      if (type === "complete") {
        await api.finishedLoadingPlanValidate(x.id);
        keys.current[type] ??= idempotency(`loading-${x.id}`);
        await api.finishedConfirmLoading(x.id, {
          acknowledge_unknown_weight: false,
          idempotency_key: keys.current[type],
        });
      }
      if (type === "dispatch") {
        keys.current[type] ??= idempotency(`dispatch-${x.id}`);
        await api.finishedDispatch(x.id, {
          idempotency_key: keys.current[type],
        });
      }
      keys.current[type] = null;
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    } finally {
      setAction("");
    }
  };
  const createTrip = async (event) => {
    event.preventDefault();
    setAction("create");
    try {
      await api.finishedConsolidatedTripCreate({
        trip_number: trip.trip_number,
        vehicle_id: Number(trip.vehicle_id),
        driver_user_id: Number(trip.driver_user_id),
        placement_ids: selected,
        planned_loading_at: trip.planned_loading_at || null,
        planned_departure_at: trip.planned_departure_at || null,
        delivery_deadline_at: trip.delivery_deadline_at || null,
        evidence_policy: trip.evidence_policy,
        completeness_required: trip.completeness_required,
        notes: trip.notes,
        idempotency_key:
           createTripKey.current ??
           (createTripKey.current = idempotency(
               `consolidated-${trip.trip_number}`
           )),
      });
      setTrip({
        ...trip,
        trip_number: "",
        project_id: "",
        vehicle_id: "",
        driver_user_id: "",
      });
      setSelected([]); 
      createTripKey.current = null;
      setShowCreate(false);
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    } finally {
      setAction("");
    }
  };
  const assignExisting = async () => {
    setAction("assign-existing");
    try {
      for (const placementId of selected)
        await api.finishedTripAssign(Number(targetTripId), {
          placement_id: placementId,
          idempotency_key: idempotency(`assign-${targetTripId}-${placementId}`),
        });
      setSelected([]);
      setTargetTripId("");
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    } finally {
      setAction("");
    }
  };
  const options = loadingOnly ? loadingViews : statuses;
  return (
    <section>
      <LogisticsSectionNav />
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">
            {t(
              loadingOnly
                ? "logisticsCenter.loading.title"
                : "logisticsCenter.shipments.title"
            )}
          </h1>
          <p className="text-sm text-[var(--brand-muted)]">
            {t(
              loadingOnly
                ? "logisticsCenter.loading.subtitle"
                : "logisticsCenter.shipments.subtitle"
            )}
          </p>
        </div>
        {!loadingOnly && (
          <button
            type="button"
            className="brand-btn rounded-xl px-4 py-2 font-bold text-white"
            onClick={() => setShowCreate(!showCreate)}
          >
            {t("checkpointD.trips.create")}
          </button>
        )}
      </header>
      {!loadingOnly && (
        <div className={`${panel} mb-4`}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <strong>{t("logisticsCenter.readyCargo.title")}</strong>
            <button
              type="button"
              disabled={!(ready.items || []).length}
              className="rounded-lg border px-3 py-1 disabled:opacity-50"
              onClick={() =>
                setSelected(
                  selected.length === (ready.items || []).length
                    ? []
                    : (ready.items || []).map((x) => x.id)
                )
              }
            >
              {t(
                (ready.items || []).length > 0 &&
                  selected.length === (ready.items || []).length
                  ? "logisticsCenter.readyCargo.clear"
                  : "logisticsCenter.readyCargo.selectAll"
              )}
            </button>
          </div>
          <div className="mb-4 max-h-80 space-y-3 overflow-y-auto">
            {(ready.projects || []).map((project) => (
              <section
                className="rounded-xl border p-3"
                key={project.project_id}
              >
                <div className="mb-2 flex justify-between gap-2">
                  <b>
  {project.project_code && project.project_code !== "#None"
    ? project.project_code
    : project.project_id
      ? `#${project.project_id}`
      : t("checkpointD.values.missing")}
  {" · "}
  {project.destination_city ||
    project.destination_site ||
    t("checkpointD.values.missing")}
</b>
                  <span>
                    {project.package_count} · {number(project.quantity, locale)}
                  </span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {(ready.items || [])
                    .filter((x) => x.project_id === project.project_id)
                    .map((item) => (
                      <label
                        className="flex items-start gap-2 rounded-lg border p-2"
                        key={item.id}
                      >
                        <input
                          type="checkbox"
                          checked={selected.includes(item.id)}
                          onChange={() =>
                            setSelected((current) =>
                              current.includes(item.id)
                                ? current.filter((x) => x !== item.id)
                                : [...current, item.id]
                            )
                          }
                        />
                        <span>
                          <b>{item.package_number || `#${item.package_id}`}</b>
                          <small className="block">
                            {item.product_code} · {item.location_code}
                          </small>
                        </span>
                      </label>
                    ))}
                </div>
              </section>
            ))}
            {!(ready.items || []).length && (
              <p className="text-sm text-[var(--brand-muted)]">
                {t("logisticsCenter.readyCargo.empty")}
              </p>
            )}
          </div>
          <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_auto]">
            <select className="rounded-xl border px-3 py-2" value={targetTripId} onChange={(e) => setTargetTripId(e.target.value)}>
              <option value="">{t("logisticsCenter.readyCargo.existingTrip")}</option>
              {rows.filter((row) => ["draft", "planned", "loading"].includes(row.status)).map((row) => <option key={row.id} value={row.id}>{row.trip_number}</option>)}
            </select>
            <button type="button" disabled={!targetTripId || !selected.length || !!action} onClick={assignExisting} className="rounded-xl border px-4 py-2 font-bold disabled:opacity-50">
              {t("logisticsCenter.readyCargo.assignExisting")}
            </button>
          </div>
        {showCreate && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createTrip}> 
            <input 
              required
              className="rounded-xl border px-3 py-2"
              placeholder={t("checkpointD.fields.trip_number")}
              value={trip.trip_number}
              onChange={(e) =>
                setTrip({ ...trip, trip_number: e.target.value })
              }
            />
            <select
              required
              className="rounded-xl border px-3 py-2"
              value={trip.vehicle_id}
              onChange={(e) => setTrip({ ...trip, vehicle_id: e.target.value })}
            >
              <option value="">{t("checkpointD.fields.vehicle")}</option>
              {vehicles
                .filter(
                  (v) => v.is_active && v.operational_state === "AVAILABLE"
                )
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.registration_number}
                  </option>
                ))}
            </select>
            <select
              required
              className="rounded-xl border px-3 py-2"
              value={trip.driver_user_id}
              onChange={(e) =>
                setTrip({ ...trip, driver_user_id: e.target.value })
              }
            >
              <option value="">{t("checkpointD.fields.driver_name")}</option>
              {drivers
                .filter((d) => d.is_active !== false)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name || d.username}
                  </option>
                ))}
            </select>
            {[
              ["planned_loading_at", "logisticsCenter.loading.plannedAt"],
              [
                "planned_departure_at",
                "checkpointD.fields.planned_departure_at",
              ],
              [
                "delivery_deadline_at",
                "checkpointD.fields.delivery_deadline_at",
              ],
            ].map(([key, label]) => (
              <label key={key} className="text-sm">
                <span className="block font-semibold">{t(label)}</span>
                <input
                  type="datetime-local"
                  className="mt-1 w-full rounded-xl border px-3 py-2"
                  value={trip[key]}
                  onChange={(e) => setTrip({ ...trip, [key]: e.target.value })}
                />
              </label>
            ))}
            <input
              className="rounded-xl border px-3 py-2"
              placeholder={t("checkpointD.fields.notes")}
              value={trip.notes}
              onChange={(e) => setTrip({ ...trip, notes: e.target.value })}
            />
            <button
              disabled={!!action || !selected.length}
              className="brand-btn rounded-xl px-4 py-2 font-bold text-white disabled:opacity-50 md:col-span-3"
            >
              {t("logisticsCenter.readyCargo.assign", {
                count: selected.length,
              })}
            </button>
          </form>
          )}
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        {options.map((x) => (
          <button
            key={x || "all"}
            type="button"
            onClick={() =>
              setParams(x ? { [loadingOnly ? "view" : "status"]: x } : {})
            }
            className={`rounded-full border px-3 py-1.5 text-sm ${
              filter === x ? "font-black text-white" : ""
            }`}
            style={
              filter === x
                ? { backgroundColor: "var(--brand-button)" }
                : undefined
            }
          >
            {loadingOnly
              ? t(`logisticsCenter.loading.views.${x}`)
              : x
              ? t(`checkpointD.status.${x}`)
              : t("logisticsCenter.all")}
          </button>
        ))}
      </div>
      {error && <ErrorAlert message={error} onRetry={load} />}{" "}
      {busy ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-3">
          {visible.map((x) => {
            const totals = x.progress?.totals || {},
              assigned = totals.assigned_quantity || 0,
              loaded = totals.loaded_quantity || 0,
              ready = assigned > 0 && loaded >= assigned,
              blocker = !assigned
                ? "noPackages"
                : !x.plan?.placements?.length
                ? "noPlan"
                : null;
            const passportSerials = (x.progress?.items || []).flatMap(
              (item) => item.passport_serials || []
            );
            return (
              <article className={panel} key={x.id}>
                <div className="flex flex-wrap justify-between gap-2">
                  <Link
                    className="font-black hover:underline"
                    to={`/logistics/shipments/${x.id}`}
                  >
                    {x.trip_number}
                  </Link>
                  <span className="rounded-full border px-2 py-1 text-xs font-bold">
                    {t(`checkpointD.status.${x.status}`)}
                  </span>
                </div>
                <div className="mt-2 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <p>
                    <b>{t("checkpointD.fields.project")}:</b>{" "}
                    {x.project?.project_code || `#${x.project_id}`}
                  </p>
                  <p>
                    <b>{t("checkpointD.fields.destination")}:</b>{" "}
                    {x.destination_city} · {x.destination_site}
                  </p>
                  <p>
                    <b>{t("checkpointD.fields.vehicle")}:</b>{" "}
                    {x.vehicle?.registration_number ||
                      t("checkpointD.values.missing")}
                  </p>
                  <p>
                    <b>{t("checkpointD.fields.driver_name")}:</b>{" "}
                    {x.driver_name_snapshot || t("checkpointD.values.missing")}
                  </p>
                  <p>
                    <b>{t("logisticsCenter.loading.plannedAt")}:</b>{" "}
                    {date(x.planned_departure_at, locale)}
                  </p>
                  <p>
                    <b>{t("logisticsCenter.loading.progress")}:</b>{" "}
                    {number(loaded, locale)} / {number(assigned, locale)}
                  </p>
                  <p>
                    <b>{t("logisticsCenter.loading.planItems")}:</b>{" "}
                    {x.plan?.placements?.length || 0}
                  </p>
                  <p>
                    <b>{t("logisticsCenter.loading.readiness")}:</b>{" "}
                    {ready
                      ? t("logisticsCenter.ready")
                      : t("logisticsCenter.blocked")}
                  </p>
                  <p>
                    <b>{t("traceability.products")}:</b>{" "}
                    {passportSerials.length}
                  </p>
                </div>
                {loadingOnly && blocker && (
                  <p className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
                    {t(`logisticsCenter.loading.blockers.${blocker}`)}
                  </p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link
                    className="rounded-xl border px-3 py-2 text-sm font-bold"
                    to={`/logistics/shipments/${x.id}`}
                  >
                    {t("logisticsCenter.open")}
                  </Link>
                  <ProductPassportActions serials={passportSerials} compact />
                  {loadingOnly && x.status === "planned" && (
                    <button
                      disabled={!!action}
                      onClick={() => run(x, "start")}
                      className="rounded-xl bg-amber-600 px-3 py-2 text-sm font-bold text-white"
                    >
                      {t("checkpointD.actions.startLoading")}
                    </button>
                  )}
                  {loadingOnly && x.status === "loading" && (
                    <button
                      disabled={!!action || !!blocker}
                      onClick={() => run(x, "complete")}
                      className="rounded-xl bg-green-700 px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
                    >
                      {t("checkpointD.actions.confirmLoading")}
                    </button>
                  )}
                  {loadingOnly && x.status === "loaded" && (
                    <button
                      disabled={!!action}
                      onClick={() => run(x, "dispatch")}
                      className="rounded-xl bg-blue-700 px-3 py-2 text-sm font-bold text-white"
                    >
                      {t("checkpointD.actions.dispatch")}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
          {!visible.length && (
            <div className={panel}>{t("logisticsCenter.empty")}</div>
          )}
        </div>
      )}
    </section>
  );
}
