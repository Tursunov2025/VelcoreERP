import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, apiDownload } from "../../api/client";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import ProductPassportActions from "../../components/traceability/ProductPassportActions";
import TripRoutePlanner from "../../components/logistics/TripRoutePlanner";
import {
  apiMessage,
  button,
  date,
  field,
  idempotency,
  number,
  panel,
} from "../productionProjects/projectUi";
const tabs = [
  "overview",
  "products",
  "projects",
  "packages",
  "loading",
  "transport",
  "route",
  "gps",
  "delivery",
  "history",
];
export default function TripDetailPage() {
  const { id } = useParams();
  const { t, locale } = useLocale();
  const yandexKey = import.meta.env.VITE_YANDEX_MAPS_API_KEY || "";
  const [tab, setTab] = useState("overview");
  const [s, setS] = useState({
    trip: null,
    progress: null,
    plan: null,
    vehicle: null,
    evidence: [],
    placements: [],
    tracking: { latest: null, history: [] },
    vehicles: [],
    drivers: [],
    trips: [],
    documents: [],
  });
  const [operations, setOperations] = useState({
    vehicle_id: "",
    driver_user_id: "",
    planned_loading_at: "",
    planned_departure_at: "",
    delivery_deadline_at: "",
  });
  const [draft, setDraft] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState(null);
  const [ack, setAck] = useState(false);
  const [delivery, setDelivery] = useState({});
  const [deliveryProject, setDeliveryProject] = useState("");
  const [correction, setCorrection] = useState({
    itemId: null,
    reason: "wrong_package",
    notes: "",
    targetTripId: "",
  });
  const [accept, setAccept] = useState({
    recipient_name: "",
    notes: "",
    resolved_shortage_item_ids: [],
  });
  const [upload, setUpload] = useState({
    evidence_type: "loading_start",
    note: "",
    latitude: "",
    longitude: "",
    file: null,
  });
  const keys = useRef({});
  const load = useCallback(async () => {
    try {
      const [
        trip,
        progress,
        plan,
        evidence,
        vehicles,
        tracking,
        drivers,
        trips,
        documents,
      ] = await Promise.all([
        api.finishedTrip(id),
        api.finishedTripProgress(id),
        api
          .finishedLoadingPlan(id)
          .catch(() => ({ placements: [], totals: {} })),
        api.finishedEvidence(id),
        api.finishedVehicles(true),
        api
          .finishedTripTracking(id)
          .catch(() => ({ latest: null, history: [] })),
        api.finishedDrivers(),
        api.finishedTrips(),
        api.finishedTripDocuments(id).catch(() => ({ documents: [] })),
      ]);
      const vehicle = vehicles.vehicles?.find((v) => v.id === trip.vehicle_id);
      const eligible = await api.finishedPlacements({ status: "placed" });
      setS({
        trip,
        progress,
        plan,
        vehicle,
        evidence: evidence.evidence || [],
        placements: eligible.placements || [],
        tracking,
        vehicles: vehicles.vehicles || [],
        drivers: drivers.drivers || [],
        trips: trips.trips || [],
        documents: documents.documents || [],
      });
      const local = (value) =>
        value ? new Date(value).toISOString().slice(0, 16) : "";
      setOperations({
        vehicle_id: trip.vehicle_id ?? "",
        driver_user_id: trip.driver_user_id ?? "",
        planned_loading_at: local(trip.planned_loading_at),
        planned_departure_at: local(trip.planned_departure_at),
        delivery_deadline_at: local(trip.delivery_deadline_at),
      });
      setDraft(plan.placements || []);
      setDirty(false);
      setDelivery(
        Object.fromEntries(
          (progress.items || []).map((x) => [
            x.id,
            {
              item_id: x.id,
              delivered_quantity: x.loaded_quantity,
              accepted_quantity: x.loaded_quantity,
              damaged_quantity: 0,
              missing_quantity: 0,
              notes: "",
            },
          ])
        )
      );
      setError("");
    } catch (e) {
      setError(apiMessage(e, t));
    }
  }, [id, t]);
  const generateDocument = async (documentType) => {
    try {
      const created = await api.finishedTripDocumentCreate(id, {
        document_type: documentType,
        language: locale,
      });
      await apiDownload(
        `/mes/finished-logistics/trip-documents/${created.id}/download`,
        created.filename
      );
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const guard = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    addEventListener("beforeunload", guard);
    return () => removeEventListener("beforeunload", guard);
  }, [dirty]);
  const trip = s.trip,
    vehicle = s.vehicle,
    items = s.progress?.items || [];
  const itemById = useMemo(
    () => Object.fromEntries(items.map((x) => [x.id, x])),
    [items]
  );
  const products = useMemo(
    () =>
      Object.values(
        items.reduce((acc, item) => {
          const key = item.product_code || `package-${item.package_id}`;
          const current = acc[key] || {
            code: item.product_code || "—",
            name: item.product_name || "—",
            quantity: 0,
            loaded: 0,
            delivered: 0,
          };
          current.quantity += Number(item.assigned_quantity || 0);
          current.loaded += Number(item.loaded_quantity || 0);
          current.delivered += Number(item.delivered_quantity || 0);
          acc[key] = current;
          return acc;
        }, {})
      ),
    [items]
  );
  const automatic = async () => {
    try {
      const r = await api.finishedLoadingPlanAutomatic(id);
      setDraft(r.placements || []);
      setDirty(true);
      setTab("loading");
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const assignPlacement = async (placementId) => {
    try {
      await api.finishedTripAssign(id, {
        placement_id: Number(placementId),
        idempotency_key: idempotency(`assign-${id}-${placementId}`),
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const transition = async (status) => {
    try {
      await api.finishedTripTransition(id, {
        status,
        expected_version: trip.version,
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const save = async () => {
    try {
      await api.finishedLoadingPlanSave(
        id,
        draft.map((x) => ({
          shipment_item_id: x.shipment_item_id,
          x_mm: x.x_mm,
          y_mm: x.y_mm,
          rotation: x.rotation,
          loading_sequence: x.loading_sequence,
          expected_version: x.version || null,
        }))
      );
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const rotate = (item) => {
    const changed = draft.map((x) =>
      x.shipment_item_id === item.shipment_item_id
        ? {
            ...x,
            rotation: x.rotation === 90 ? 0 : 90,
            placed_width_mm: x.placed_length_mm,
            placed_length_mm: x.placed_width_mm,
          }
        : x
    );
    setDraft(changed);
    setDirty(true);
  };
  const drag = (event, p) => {
    if (!vehicle) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const svg = event.currentTarget.ownerSVGElement;
    const move = (e) => {
      const box = svg.getBoundingClientRect();
      const x = Math.max(
        0,
        Math.min(
          vehicle.internal_width_mm - p.placed_width_mm,
          ((e.clientX - box.left) / box.width) * vehicle.internal_width_mm
        )
      );
      const y = Math.max(
        0,
        Math.min(
          vehicle.internal_length_mm - p.placed_length_mm,
          ((e.clientY - box.top) / box.height) * vehicle.internal_length_mm
        )
      );
      setDraft((d) =>
        d.map((a) =>
          a.shipment_item_id === p.shipment_item_id
            ? { ...a, x_mm: Math.round(x), y_mm: Math.round(y) }
            : a
        )
      );
      setDirty(true);
    };
    const up = () => {
      svg.removeEventListener("pointermove", move);
      svg.removeEventListener("pointerup", up);
    };
    svg.addEventListener("pointermove", move);
    svg.addEventListener("pointerup", up);
  };
  const command = async (type) => {
    setConfirm(null);
    keys.current[type] ??= idempotency(`${type}-${id}`);
    try {
      if (type === "loading")
        await api.finishedConfirmLoading(id, {
          acknowledge_unknown_weight: ack,
          idempotency_key: keys.current[type],
        });
      if (type === "dispatch")
        await api.finishedDispatch(id, { idempotency_key: keys.current[type] });
      if (type === "arrival")
        await api.finishedArrival(id, {
          expected_version: trip.version,
          idempotency_key: keys.current[type],
        });
      if (type === "acceptance")
        await api.finishedAcceptance(id, {
          ...accept,
          idempotency_key: keys.current[type],
        });
      keys.current[type] = null;
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const submitDelivery = async () => {
    const dispositions = Object.values(delivery).filter(
      (row) =>
        !deliveryProject ||
        itemById[row.item_id]?.project_id === Number(deliveryProject)
    );
    if (
      dispositions.some(
        (x) =>
          Number(x.delivered_quantity) !==
          Number(x.accepted_quantity) +
            Number(x.damaged_quantity) +
            Number(x.missing_quantity)
      )
    ) {
      setError(t("checkpointD.delivery.balanceError"));
      return;
    }
    keys.current.delivery ??= idempotency(`delivery-${id}`);
    try {
      await api.finishedDelivery(id, {
        dispositions,
        idempotency_key: keys.current.delivery,
      });
      keys.current.delivery = null;
      load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const runCorrection = async (item, type) => {
    const body = {
      expected_trip_version: trip.version,
      expected_item_version: item.version,
      reason: correction.reason,
      notes: correction.notes,
      idempotency_key: idempotency(`${type}-${id}-${item.id}`),
    };
    try {
      if (type === "unload") await api.finishedUnload(id, item.id, body);
      if (type === "return")
        await api.finishedReturnToWarehouse(id, item.id, body);
      if (type === "reload") await api.finishedReload(id, item.id, body);
      if (type === "transfer") {
        const target = s.trips.find(
          (x) => x.id === Number(correction.targetTripId)
        );
        await api.finishedTransfer(id, item.id, {
          ...body,
          target_trip_id: target.id,
          expected_target_trip_version: target.version,
        });
      }
      setCorrection({
        itemId: null,
        reason: "wrong_package",
        notes: "",
        targetTripId: "",
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const uploadEvidence = async (e) => {
    e.preventDefault();
    const f = new FormData();
    f.append("evidence_type", upload.evidence_type);
    f.append("note", upload.note);
    if (upload.latitude !== "") f.append("latitude", upload.latitude);
    if (upload.longitude !== "") f.append("longitude", upload.longitude);
    f.append("file", upload.file);
    try {
      await api.finishedEvidenceUpload(id, f);
      setUpload({ ...upload, note: "", file: null });
      load();
    } catch (err) {
      setError(apiMessage(err, t));
    }
  };
  const saveAssignment = async () => {
    try {
      await api.finishedTripAssignmentUpdate(id, {
        expected_version: trip.version,
        vehicle_id:
          operations.vehicle_id === "" ? null : Number(operations.vehicle_id),
        driver_user_id:
          operations.driver_user_id === ""
            ? null
            : Number(operations.driver_user_id),
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const savePlanning = async () => {
    const iso = (v) => (v ? new Date(v).toISOString() : null);
    try {
      await api.finishedTripPlanningUpdate(id, {
        expected_version: trip.version,
        planned_loading_at: iso(operations.planned_loading_at),
        planned_departure_at: iso(operations.planned_departure_at),
        delivery_deadline_at: iso(operations.delivery_deadline_at),
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  if (!trip)
    return (
      <div className={panel}>{error || t("checkpointD.actions.loading")}</div>
    );
  const totals = s.plan?.totals || {};
  return (
    <section className="min-w-0 space-y-4">
      <header>
        <h1 className="text-2xl font-black">{trip.trip_number}</h1>
        <p>
          {trip.destination_city} · {t(`checkpointD.status.${trip.status}`)} ·{" "}
          {trip.driver_name_snapshot || t("checkpointD.values.missing")}
        </p>
      </header>
      {error && <ErrorAlert message={error} onRetry={load} />}
      {(trip.alerts || []).length > 0 && (
        <div className="grid gap-2">
          {trip.alerts.map((alert) => (
            <p
              className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
              key={alert.type}
            >
              {t(`logisticsCenter.alerts.${alert.type}`)}
            </p>
          ))}
        </div>
      )}
      <nav className="flex gap-2 overflow-x-auto pb-1">
        {tabs.map((x) => (
          <button
            key={x}
            onClick={() => setTab(x)}
            className={`whitespace-nowrap rounded-xl px-3 py-2 ${
              tab === x ? "brand-btn text-white" : "border"
            }`}
          >
            {x === "route" ? t("tripRoute.tab") : t(`checkpointD.tripTabs.${x}`)}
          </button>
        ))}
      </nav>
      {tab === "overview" && (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["vehicle", vehicle?.registration_number],
              [
                "payload",
                vehicle ? `${number(vehicle.max_payload_kg, locale)} kg` : "—",
              ],
              [
                "dimensions",
                vehicle
                  ? `${vehicle.internal_length_mm} × ${vehicle.internal_width_mm} × ${vehicle.internal_height_mm} mm`
                  : "—",
              ],
              ["departure", date(trip.planned_departure_at, locale)],
              ["plannedLoading", date(trip.planned_loading_at, locale)],
              ["deadline", date(trip.delivery_deadline_at, locale)],
              ["sla", t(`logisticsCenter.sla.${trip.sla_state}`)],
              [
                "evidencePolicy",
                t(`checkpointD.policy.${trip.evidence_policy}`),
              ],
              [
                "destination",
                `${trip.destination_city} · ${trip.destination_site}`,
              ],
            ].map(([k, v]) => (
              <div className={panel} key={k}>
                <small>{t(`checkpointD.fields.${k}`)}</small>
                <strong className="block">{v || "—"}</strong>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {trip.status === "draft" && (
              <button
                className={`${button} bg-sky-600`}
                onClick={() => transition("planned")}
              >
                {t("checkpointD.actions.plan")}
              </button>
            )}
            {trip.status === "planned" && (
              <button
                className={`${button} bg-amber-600`}
                onClick={() => transition("loading")}
              >
                {t("checkpointD.actions.startLoading")}
              </button>
            )}
            {trip.status === "dispatched" && (
              <button
                className={`${button} bg-blue-600`}
                onClick={() => transition("in_transit")}
              >
                {t("checkpointD.actions.inTransit")}
              </button>
            )}
            {trip.status === "in_transit" && (
              <button
                className={`${button} bg-indigo-600`}
                onClick={() => setConfirm("arrival")}
              >
                {t("checkpointD.actions.confirmArrival")}
              </button>
            )}
          </div>
          <section className={panel}>
            <h2 className="font-black">{t("logisticsCenter.documents.title")}</h2>
            <p className="mt-1 text-sm text-[var(--brand-muted)]">
              {t("logisticsCenter.documents.hint")}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {["packing_list", "loading_list", "trip_manifest", "delivery_note"].map((type) => (
                <button key={type} type="button" className={`${button} bg-slate-700`} onClick={() => generateDocument(type)}>
                  {t(`logisticsCenter.documents.${type}`)}
                </button>
              ))}
            </div>
            {s.documents.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                {s.documents.map((doc) => (
                  <button key={doc.id} type="button" className="rounded-lg border px-3 py-2" onClick={() => apiDownload(`/mes/finished-logistics/trip-documents/${doc.id}/download`, doc.filename)}>
                    {t(`logisticsCenter.documents.${doc.document_type}`)} · v{doc.version}
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
      {tab === "products" && (
        <div className={panel}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr>
                  {["product", "quantity", "loaded", "delivered"].map((x) => (
                    <th className="p-2 text-left" key={x}>
                      {t(`checkpointD.fields.${x}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {products.map((x) => (
                  <tr className="border-t" key={x.code}>
                    <td className="p-2">
                      <strong>{x.code}</strong>
                      <span className="block text-[var(--brand-muted)]">
                        {x.name}
                      </span>
                    </td>
                    <td className="p-2">{number(x.quantity, locale)}</td>
                    <td className="p-2">{number(x.loaded, locale)}</td>
                    <td className="p-2">{number(x.delivered, locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {tab === "projects" && (
        <div className="grid gap-3 md:grid-cols-2">
          {(s.progress?.projects || []).map((project) => (
            <article className={panel} key={project.project_id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <strong>{project.project_code}</strong>
                  <p className="text-sm text-[var(--brand-muted)]">
                    {project.project_name || project.destination_city} ·{" "}
                    {project.destination_site}
                  </p>
                </div>
                <span className="rounded-full border px-2 py-1 text-xs font-bold">
                  {project.package_count}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <p>
                  {t("checkpointD.fields.quantity")}:{" "}
                  <b>{number(project.assigned_quantity, locale)}</b>
                </p>
                <p>
                  {t("checkpointD.fields.loaded")}:{" "}
                  <b>{number(project.loaded_quantity, locale)}</b>
                </p>
                <p>
                  {t("checkpointD.fields.delivered")}:{" "}
                  <b>{number(project.delivered_quantity, locale)}</b>
                </p>
                <p>
                  {t("checkpointD.fields.accepted")}:{" "}
                  <b>{number(project.accepted_quantity, locale)}</b>
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
      {tab === "packages" && (
        <div className={panel}>
          {["draft", "planned"].includes(trip.status) &&
            s.placements.length > 0 && (
              <div className="mb-4">
                <h2 className="font-black">
                  {t("checkpointD.items.eligible")}
                </h2>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {s.placements.map((placement) => (
                    <button
                      key={placement.id}
                      type="button"
                      onClick={() => assignPlacement(placement.id)}
                      className="rounded-xl border p-3 text-left hover:bg-black/5"
                    >
                      <strong>
                        {placement.package_number || `#${placement.package_id}`}
                      </strong>{" "}
                      · {placement.product_code}
                      <span className="block text-sm text-[var(--brand-muted)]">
                        {number(placement.quantity, locale)} ·{" "}
                        {placement.location_code}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-sm">
              <thead>
                <tr>
                  {[
                    "package",
                    "quantity",
                    "weight",
                    "dimensions",
                    "loaded",
                    "delivered",
                    "accepted",
                    "status",
                  ].map((x) => (
                    <th className="p-2 text-left" key={x}>
                      {t(`checkpointD.fields.${x}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...items, ...(s.progress?.inactive_items || [])].map((x) => (
                  <tr className="border-t" key={x.id}>
                    <td className="p-2">
                      <span>{x.package_number || `#${x.package_id}`}</span>
                      <ProductPassportActions
                        packageId={x.package_id}
                        serials={x.passport_serials || []}
                        compact
                      />
                    </td>
                    <td className="p-2">
                      {number(x.assigned_quantity, locale)}
                    </td>
                    <td className="p-2">
                      {x.gross_weight_kg == null
                        ? t("checkpointD.values.unknownWeight")
                        : `${number(x.gross_weight_kg, locale)} kg`}
                    </td>
                    <td className="p-2">
                      {x.length_mm && x.width_mm
                        ? `${x.length_mm} × ${x.width_mm} × ${x.height_mm} mm`
                        : t("checkpointD.values.missing")}
                    </td>
                    <td className="p-2">{number(x.loaded_quantity, locale)}</td>
                    <td className="p-2">
                      {number(x.delivered_quantity, locale)}
                    </td>
                    <td className="p-2">
                      {number(x.accepted_quantity, locale)}
                    </td>
                    <td className="p-2">
                      <span className="block">
                        {t(
                          `logisticsCenter.corrections.states.${
                            x.assignment_status || "active"
                          }`
                        )}
                      </span>
                      {["loading", "loaded"].includes(trip.status) && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {x.assignment_status === "active" &&
                            x.loaded_quantity > 0 && (
                              <>
                                <button
                                  type="button"
                                  className="rounded-lg border px-2 py-1"
                                  onClick={() =>
                                    setCorrection({
                                      ...correction,
                                      itemId: x.id,
                                    })
                                  }
                                >
                                  {t("logisticsCenter.corrections.correct")}
                                </button>
                              </>
                            )}
                          {["unloaded", "hold"].includes(
                            x.assignment_status
                          ) && (
                            <button
                              type="button"
                              className="rounded-lg border px-2 py-1"
                              onClick={() => runCorrection(x, "return")}
                            >
                              {t("logisticsCenter.corrections.return")}
                            </button>
                          )}
                          {["unloaded", "returned"].includes(
                            x.assignment_status
                          ) && (
                            <button
                              type="button"
                              className="rounded-lg border px-2 py-1"
                              onClick={() => runCorrection(x, "reload")}
                            >
                              {t("logisticsCenter.corrections.reload")}
                            </button>
                          )}
                        </div>
                      )}
                      {correction.itemId === x.id && (
                        <div className="mt-2 min-w-56 space-y-2 rounded-xl border p-2">
                          <select
                            className={field}
                            value={correction.reason}
                            onChange={(e) =>
                              setCorrection({
                                ...correction,
                                reason: e.target.value,
                              })
                            }
                          >
                            {[
                              "wrong_package",
                              "wrong_truck",
                              "wrong_destination",
                              "damaged_before_dispatch",
                              "capacity_correction",
                              "customer_change",
                              "other",
                            ].map((reason) => (
                              <option key={reason} value={reason}>
                                {t(
                                  `logisticsCenter.corrections.reasons.${reason}`
                                )}
                              </option>
                            ))}
                          </select>
                          <input
                            className={field}
                            value={correction.notes}
                            onChange={(e) =>
                              setCorrection({
                                ...correction,
                                notes: e.target.value,
                              })
                            }
                            placeholder={t("checkpointD.fields.notes")}
                          />
                          <select
                            className={field}
                            value={correction.targetTripId}
                            onChange={(e) =>
                              setCorrection({
                                ...correction,
                                targetTripId: e.target.value,
                              })
                            }
                          >
                            <option value="">
                              {t("logisticsCenter.corrections.target")}
                            </option>
                            {s.trips
                              .filter(
                                (row) =>
                                  row.id !== trip.id &&
                                  ["planned", "loading"].includes(row.status)
                              )
                              .map((row) => (
                                <option key={row.id} value={row.id}>
                                  {row.trip_number}
                                </option>
                              ))}
                          </select>
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className="rounded-lg border px-2 py-1"
                              onClick={() => runCorrection(x, "unload")}
                            >
                              {t("logisticsCenter.corrections.unload")}
                            </button>
                            <button
                              type="button"
                              disabled={!correction.targetTripId}
                              className="rounded-lg border px-2 py-1 disabled:opacity-50"
                              onClick={() => runCorrection(x, "transfer")}
                            >
                              {t("logisticsCenter.corrections.transfer")}
                            </button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {tab === "gps" && (
        <div className={panel}>
          <h2 className="font-black">{t("checkpointD.tracking.title")}</h2>
          {s.tracking.latest ? (
            <>
              <p className="mt-2 text-sm">
                {t("checkpointD.tracking.latest")}:{" "}
                {date(s.tracking.latest.captured_at, locale)}
              </p>
              <p>
                {Number(s.tracking.latest.latitude).toFixed(6)},{" "}
                {Number(s.tracking.latest.longitude).toFixed(6)}
              </p>
              {yandexKey ? (
                <>
                  <a
                    className="mt-3 inline-block rounded-xl border px-3 py-2"
                    target="_blank"
                    rel="noreferrer"
                    href={`https://yandex.com/maps/?pt=${s.tracking.latest.longitude},${s.tracking.latest.latitude}&z=15&l=map`}
                  >
                    {t("checkpointD.tracking.openYandex")}
                  </a>
                  <div className="mt-4 h-80 overflow-hidden rounded-xl border">
                    <iframe
                      title={t("checkpointD.tracking.mapTitle")}
                      className="h-full w-full"
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      src={`https://yandex.com/map-widget/v1/?ll=${s.tracking.latest.longitude}%2C${s.tracking.latest.latitude}&z=15&pt=${s.tracking.latest.longitude}%2C${s.tracking.latest.latitude},pm2rdm`}
                    />
                  </div>
                </>
              ) : (
                <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-900">
                  {t("checkpointD.tracking.yandexMissing")}
                </p>
              )}
              <p className="mt-3 text-sm text-[var(--brand-muted)]">
                {t("checkpointD.tracking.points", {
                  count: s.tracking.history.length,
                })}
              </p>
            </>
          ) : (
            <p className="mt-2 text-[var(--brand-muted)]">
              {t("checkpointD.tracking.empty")}
            </p>
          )}
        </div>
      )}
      {tab === "route" && <TripRoutePlanner tripId={id} />}
      {tab === "loading" && (
        <div className="grid min-w-0 gap-4 xl:grid-cols-[1fr_300px]">
          <div className={panel}>
            <div className="mb-3 flex flex-wrap gap-2">
              <button
                className="rounded-xl border px-3 py-2"
                onClick={automatic}
              >
                {t("checkpointD.plan.automatic")}
              </button>
              <button
                className="rounded-xl border px-3 py-2"
                disabled={!dirty}
                onClick={save}
              >
                {t("checkpointD.actions.save")}
              </button>
              <button
                className="rounded-xl border px-3 py-2"
                onClick={async () => {
                  try {
                    await api.finishedLoadingPlanValidate(id);
                    setError("");
                  } catch (e) {
                    setError(apiMessage(e, t));
                  }
                }}
              >
                {t("checkpointD.actions.validate")}
              </button>
              <button
                className="rounded-xl border px-3 py-2"
                onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
              >
                ＋
              </button>
              <button
                className="rounded-xl border px-3 py-2"
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
              >
                −
              </button>
              <button
                className="rounded-xl border px-3 py-2"
                onClick={() => setZoom(1)}
              >
                {t("checkpointD.plan.resetView")}
              </button>
            </div>
            {vehicle ? (
              <div className="max-w-full overflow-auto">
                <svg
                  role="application"
                  aria-label={t("checkpointD.plan.canvas")}
                  viewBox={`0 0 ${vehicle.internal_width_mm} ${vehicle.internal_length_mm}`}
                  style={{
                    width: `${
                      Math.max(420, vehicle.internal_width_mm / 6) * zoom
                    }px`,
                    maxWidth: "none",
                    aspectRatio: `${vehicle.internal_width_mm}/${vehicle.internal_length_mm}`,
                  }}
                  className="border-4 border-slate-700 bg-slate-100"
                >
                  <text x="20" y="35" fontSize="28" fill="#334155">
                    {vehicle.internal_width_mm} mm ×{" "}
                    {vehicle.internal_length_mm} mm
                  </text>
                  {draft.map((p) => (
                    <g
                      key={p.shipment_item_id}
                      transform={`translate(${p.x_mm} ${p.y_mm})`}
                      onPointerDown={(e) => drag(e, p)}
                      onClick={() => setSelected(p)}
                      className="cursor-move"
                    >
                      <rect
                        width={p.placed_width_mm}
                        height={p.placed_length_mm}
                        fill={
                          selected?.shipment_item_id === p.shipment_item_id
                            ? "#2563eb"
                            : "#0f766e"
                        }
                        stroke="white"
                        strokeWidth="8"
                      />
                      <text x="15" y="35" fill="white" fontSize="26">
                        #{itemById[p.shipment_item_id]?.package_id} ·{" "}
                        {itemById[p.shipment_item_id]?.gross_weight_kg ?? "?"}{" "}
                        kg
                      </text>
                      <text x="15" y="67" fill="white" fontSize="22">
                        {p.loading_sequence} · {p.rotation}°
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
            ) : (
              <p>{t("checkpointD.plan.noVehicle")}</p>
            )}
            <p className="mt-2 text-sm text-amber-700">
              {t("checkpointD.plan.notOptimal")}
            </p>
            {dirty && (
              <p className="text-sm font-bold text-red-600">
                {t("checkpointD.plan.unsaved")}
              </p>
            )}
          </div>
          <aside className="space-y-3">
            <div className={panel}>
              <h3 className="font-black">{t("checkpointD.plan.totals")}</h3>
              {[
                ["package_count", "package_count"],
                ["product_quantity", "product_quantity"],
                ["known_gross_weight_kg", "known_gross_weight_kg"],
                ["unknown_weight_count", "unknown_weight_item_count"],
                ["remaining_known_payload_kg", "remaining_known_payload_kg"],
                ["occupied_floor_area_mm2", "occupied_floor_area_mm2"],
                ["utilization_percent", "floor_utilization_percent"],
              ].map(([labelKey, valueKey]) => (
                <p className="flex justify-between" key={labelKey}>
                  <span>{t(`checkpointD.metrics.${labelKey}`)}</span>
                  <strong>{number(totals[valueKey], locale)}</strong>
                </p>
              ))}
            </div>
            {selected && (
              <div className={panel}>
                <h3 className="font-black">{t("checkpointD.plan.selected")}</h3>
                <p>#{itemById[selected.shipment_item_id]?.package_id}</p>
                <p>
                  {selected.x_mm}, {selected.y_mm} mm
                </p>
                <button
                  className="mt-2 rounded-xl border px-3 py-2"
                  onClick={() => rotate(selected)}
                >
                  {t("checkpointD.plan.rotate")}
                </button>
              </div>
            )}
            <label className={`${panel} flex gap-2`}>
              <input
                type="checkbox"
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
              />
              {t("checkpointD.plan.ackUnknown")}
            </label>
            {trip.status === "loading" && (
              <button
                className={`${button} w-full bg-emerald-600`}
                onClick={() => setConfirm("loading")}
              >
                {t("checkpointD.actions.confirmLoading")}
              </button>
            )}
          </aside>
        </div>
      )}
      {tab === "transport" && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["vehicle", vehicle?.registration_number],
              ["driver", trip.driver_name_snapshot],
              [
                "payload",
                vehicle ? `${number(vehicle.max_payload_kg, locale)} kg` : "—",
              ],
              [
                "dimensions",
                vehicle
                  ? `${vehicle.internal_length_mm} × ${vehicle.internal_width_mm} × ${vehicle.internal_height_mm} mm`
                  : "—",
              ],
              ["departure", date(trip.planned_departure_at, locale)],
              [
                "destination",
                `${trip.destination_city} · ${trip.destination_site}`,
              ],
            ].map(([k, v]) => (
              <div className={panel} key={k}>
                <small>{t(`checkpointD.fields.${k}`)}</small>
                <strong className="block">{v || "—"}</strong>
              </div>
            ))}
          </div>
          {["draft", "planned"].includes(trip.status) && (
            <div className={panel}>
              <h2 className="font-black">
                {t("logisticsCenter.assignment.title")}
              </h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <select
                  className={field}
                  value={operations.vehicle_id}
                  onChange={(e) =>
                    setOperations({ ...operations, vehicle_id: e.target.value })
                  }
                >
                  <option value="">
                    {t("logisticsCenter.assignment.noVehicle")}
                  </option>
                  {s.vehicles
                    .filter(
                      (v) => v.operational_state === "AVAILABLE" && v.is_active
                    )
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.registration_number}
                      </option>
                    ))}
                </select>
                <select
                  className={field}
                  value={operations.driver_user_id}
                  onChange={(e) =>
                    setOperations({
                      ...operations,
                      driver_user_id: e.target.value,
                    })
                  }
                >
                  <option value="">
                    {t("logisticsCenter.assignment.noDriver")}
                  </option>
                  {s.drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name || d.username}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="brand-btn mt-3 rounded-xl px-4 py-2 font-bold text-white"
                onClick={saveAssignment}
              >
                {t("logisticsCenter.assignment.save")}
              </button>
            </div>
          )}
          {["draft", "planned", "loading"].includes(trip.status) && (
            <div className={panel}>
              <h2 className="font-black">
                {t("logisticsCenter.planning.title")}
              </h2>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {[
                  "planned_loading_at",
                  "planned_departure_at",
                  "delivery_deadline_at",
                ].map((k) => (
                  <label key={k}>
                    <span className="text-xs">
                      {t(`logisticsCenter.planning.${k}`)}
                    </span>
                    <input
                      className={field}
                      type="datetime-local"
                      value={operations[k]}
                      onInput={(e) => {
                        const value = e.currentTarget.value;
                        setOperations((current) => ({
                          ...current,
                          [k]: value,
                        }));
                      }}
                    />
                  </label>
                ))}
              </div>
              <button
                className="brand-btn mt-3 rounded-xl px-4 py-2 font-bold text-white"
                onClick={savePlanning}
              >
                {t("logisticsCenter.planning.save")}
              </button>
            </div>
          )}
        </div>
      )}
      {tab === "history" && (
        <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <form className={panel} onSubmit={uploadEvidence}>
            <h2 className="font-black">{t("checkpointD.evidence.upload")}</h2>
            <select
              className={`${field} mt-3`}
              value={upload.evidence_type}
              onChange={(e) =>
                setUpload({ ...upload, evidence_type: e.target.value })
              }
            >
              {[
                "loading_start",
                "loaded_truck_photo",
                "seal_vehicle",
                "departure_photo",
                "arrival_photo",
                "unloading_photo",
                "acceptance_photo",
                "pod_document",
              ].map((x) => (
                <option key={x} value={x}>
                  {t(`checkpointD.evidence.${x}`)}
                </option>
              ))}
            </select>
            <input
              className={`${field} mt-3`}
              type="file"
              required
              accept={
                upload.evidence_type === "pod_document"
                  ? "application/pdf"
                  : "image/jpeg,image/png,image/webp"
              }
              onChange={(e) =>
                setUpload({ ...upload, file: e.target.files[0] })
              }
            />
            <p className="mt-1 text-xs text-[var(--brand-muted)]">
              {t("checkpointD.evidence.policy")}
            </p>
            <textarea
              className={`${field} mt-3`}
              placeholder={t("checkpointD.fields.notes")}
              value={upload.note}
              onChange={(e) => setUpload({ ...upload, note: e.target.value })}
            />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <input
                className={field}
                type="number"
                step="any"
                placeholder={t("checkpointD.fields.latitude")}
                value={upload.latitude}
                onChange={(e) =>
                  setUpload({ ...upload, latitude: e.target.value })
                }
              />
              <input
                className={field}
                type="number"
                step="any"
                placeholder={t("checkpointD.fields.longitude")}
                value={upload.longitude}
                onChange={(e) =>
                  setUpload({ ...upload, longitude: e.target.value })
                }
              />
            </div>
            <button className="brand-btn mt-3 w-full rounded-xl px-4 py-2 font-bold text-white">
              {t("checkpointD.actions.upload")}
            </button>
          </form>
          <div className="grid gap-3 sm:grid-cols-2">
            {s.evidence.map((x) => (
              <article className={panel} key={x.id}>
                <strong>{t(`checkpointD.evidence.${x.evidence_type}`)}</strong>
                <p>{x.original_filename}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {date(x.occurred_at, locale)} · {x.actor}
                </p>
                <button
                  className="mt-2 rounded-xl border px-3 py-2"
                  onClick={() =>
                    apiDownload(
                      `/mes/finished-logistics/evidence/${x.id}/download`,
                      x.original_filename
                    )
                  }
                >
                  {t("checkpointD.actions.download")}
                </button>
              </article>
            ))}
          </div>
        </div>
      )}
      {tab === "delivery" && (
        <div className="space-y-4">
          <div className={panel}>
            <h2 className="font-black">{t("checkpointD.delivery.title")}</h2>
            <select
              className={`${field} mt-3`}
              value={deliveryProject}
              onChange={(e) => setDeliveryProject(e.target.value)}
            >
              <option value="">{t("logisticsCenter.all")}</option>
              {(s.progress?.projects || []).map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.project_code}
                </option>
              ))}
            </select>
            {items
              .filter(
                (x) =>
                  !deliveryProject || x.project_id === Number(deliveryProject)
              )
              .map((x) => (
                <div
                  className="mt-3 grid gap-2 rounded-xl border p-3 md:grid-cols-6"
                  key={x.id}
                >
                  <strong>
                    #{x.package_id}
                    <br />
                    {t("checkpointD.fields.loaded")}:{" "}
                    {number(x.loaded_quantity, locale)}
                  </strong>
                  {[
                    "delivered_quantity",
                    "accepted_quantity",
                    "damaged_quantity",
                    "missing_quantity",
                  ].map((k) => (
                    <label key={k}>
                      <span className="text-xs">
                        {t(`checkpointD.metrics.${k}`)}
                      </span>
                      <input
                        className={field}
                        type="number"
                        min="0"
                        step="0.01"
                        value={delivery[x.id]?.[k] ?? 0}
                        onChange={(e) =>
                          setDelivery({
                            ...delivery,
                            [x.id]: {
                              ...delivery[x.id],
                              [k]: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                  ))}
                  <input
                    className={field}
                    placeholder={t("checkpointD.fields.notes")}
                    value={delivery[x.id]?.notes || ""}
                    onChange={(e) =>
                      setDelivery({
                        ...delivery,
                        [x.id]: { ...delivery[x.id], notes: e.target.value },
                      })
                    }
                  />
                </div>
              ))}
            {["in_transit", "arrived"].includes(trip.status) && (
              <button
                className="brand-btn mt-3 rounded-xl px-4 py-2 font-bold text-white"
                onClick={submitDelivery}
              >
                {t("checkpointD.actions.recordDelivery")}
              </button>
            )}
          </div>
          {["in_transit", "arrived", "delivered"].includes(trip.status) &&
            (s.progress?.projects || []).some(
              (project) =>
                project.delivered_quantity >= project.assigned_quantity
            ) && (
              <div className={panel}>
                <h2 className="font-black">
                  {t("checkpointD.delivery.acceptance")}
                </h2>
                <input
                  className={`${field} mt-3`}
                  required
                  placeholder={t("checkpointD.fields.recipient")}
                  value={accept.recipient_name}
                  onChange={(e) =>
                    setAccept({ ...accept, recipient_name: e.target.value })
                  }
                />
                <select
                  className={`${field} mt-3`}
                  value={accept.project_id || ""}
                  onChange={(e) =>
                    setAccept({
                      ...accept,
                      project_id: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">{t("logisticsCenter.all")}</option>
                  {(s.progress?.projects || [])
                    .filter(
                      (project) =>
                        project.delivered_quantity >=
                          project.assigned_quantity &&
                        project.accepted_quantity < project.assigned_quantity
                    )
                    .map((project) => (
                      <option
                        key={project.project_id}
                        value={project.project_id}
                      >
                        {project.project_code}
                      </option>
                    ))}
                </select>
                <textarea
                  className={`${field} mt-3`}
                  placeholder={t("checkpointD.fields.notes")}
                  value={accept.notes}
                  onChange={(e) =>
                    setAccept({ ...accept, notes: e.target.value })
                  }
                />
                <button
                  className={`${button} mt-3 bg-emerald-600`}
                  disabled={!accept.recipient_name}
                  onClick={() => setConfirm("acceptance")}
                >
                  {t("checkpointD.actions.finalAcceptance")}
                </button>
              </div>
            )}
        </div>
      )}
      {tab === "history" && (
        <ol className={`${panel} border-l-4`}>
          {(s.progress?.history || []).map((x, i) => (
            <li className="mb-4 pl-3" key={`${x.kind}-${x.id}-${i}`}>
              <strong>{t(`checkpointD.history.${x.type}`)}</strong>
              <p className="text-sm">
                {x.actor} · {date(x.at, locale)}
              </p>
            </li>
          ))}
        </ol>
      )}
      {trip.status === "loaded" && (
        <button
          className={`${button} bg-blue-600`}
          onClick={() => setConfirm("dispatch")}
        >
          {t("checkpointD.actions.dispatch")}
        </button>
      )}
      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm ? t(`checkpointD.dialogs.${confirm}Title`) : ""}
        message={confirm ? t(`checkpointD.dialogs.${confirm}Message`) : ""}
        confirmLabel={t("checkpointD.actions.confirm")}
        cancelLabel={t("checkpointD.actions.cancel")}
        onCancel={() => setConfirm(null)}
        onConfirm={() => command(confirm)}
      />
    </section>
  );
}
