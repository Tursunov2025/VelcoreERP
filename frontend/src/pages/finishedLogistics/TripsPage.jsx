import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import {
  apiMessage,
  date,
  field,
  number,
  panel,
} from "../productionProjects/projectUi";
export default function TripsPage() {
  const { t, locale } = useLocale();
  const [trips, setTrips] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [projects, setProjects] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [error, setError] = useState("");
  const [showVehicle, setShowVehicle] = useState(false);
  const [vehicle, setVehicle] = useState({
    vehicle_type: "",
    registration_number: "",
    driver_name: "",
    driver_phone: "",
    max_payload_kg: "",
    internal_length_mm: "",
    internal_width_mm: "",
    internal_height_mm: "",
    max_volume_m3: "",
    is_active: true,
  });
  const [trip, setTrip] = useState({
    trip_number: "",
    project_id: "",
    release_id: "",
    vehicle_id: "",
    driver_user_id: "",
    planned_departure_at: "",
    evidence_policy: "required",
    completeness_required: true,
    notes: "",
  });
  const load = useCallback(async () => {
    try {
      const [a, b, c, d] = await Promise.all([
        api.finishedTrips(),
        api.finishedVehicles(true),
        api.productionProjects({ page_size: 100 }),
        api.finishedDrivers(),
      ]);
      setTrips(a.trips || []);
      setVehicles(b.vehicles || []);
      setProjects(c.items || []);
      setDrivers(d.drivers || []);
      setError("");
    } catch (e) {
      setError(apiMessage(e, t));
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load]);
  const createVehicle = async (e) => {
    e.preventDefault();
    try {
      await api.finishedVehicleCreate(
        Object.fromEntries(
          Object.entries(vehicle).map(([k, v]) => [
            k,
            [
              "max_payload_kg",
              "internal_length_mm",
              "internal_width_mm",
              "internal_height_mm",
              "max_volume_m3",
            ].includes(k)
              ? v === ""
                ? null
                : Number(v)
              : v,
          ])
        )
      );
      setShowVehicle(false);
      load();
    } catch (e2) {
      setError(apiMessage(e2, t));
    }
  };
  const createTrip = async (e) => {
    e.preventDefault();
    const p = projects.find((x) => x.id === Number(trip.project_id));
    try {
      const requirements = await api.productionProjectRequirements(p.id);
      await api.finishedTripCreate({
        ...trip,
        project_id: Number(trip.project_id),
        release_id: Number(requirements.release?.id),
        vehicle_id: Number(trip.vehicle_id),
        driver_user_id: Number(trip.driver_user_id),
        destination_city: p.destination_city,
        destination_site: p.site_name,
        destination_address: p.full_address,
        planned_departure_at: trip.planned_departure_at || null,
      });
      setTrip({
        ...trip,
        trip_number: "",
        project_id: "",
        release_id: "",
        vehicle_id: "",
        driver_user_id: "",
      });
      load();
    } catch (e2) {
      setError(apiMessage(e2, t));
    }
  };
  return (
    <section className="space-y-4">
      <header className="flex justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">
            {t("checkpointD.trips.title")}
          </h1>
          <p className="text-sm text-[var(--brand-muted)]">
            {t("checkpointD.trips.subtitle")}
          </p>
        </div>
        <button
          className="rounded-xl border px-4 py-2"
          onClick={() => setShowVehicle(!showVehicle)}
        >
          {t("checkpointD.vehicles.manage")}
        </button>
        <Link className="rounded-xl border px-4 py-2" to="/mes/finished-logistics/fleet">{t("checkpointD.tracking.fleetTitle")}</Link>
      </header>
      {error && <ErrorAlert message={error} onRetry={load} />}{" "}
      {showVehicle && (
        <div className={panel}>
          <h2 className="font-black">{t("checkpointD.vehicles.title")}</h2>
          <form
            onSubmit={createVehicle}
            className="mt-3 grid gap-3 md:grid-cols-4"
          >
            {Object.keys(vehicle)
              .filter((k) => k !== "is_active")
              .map((k) => (
                <label key={k}>
                  <span className="text-sm">
                    {t(`checkpointD.fields.${k}`)}
                  </span>
                  <input
                    className={field}
                    required={
                      ![
                        "driver_name",
                        "driver_phone",
                        "max_volume_m3",
                      ].includes(k)
                    }
                    type={
                      k.includes("kg") || k.includes("mm") || k.includes("m3")
                        ? "number"
                        : "text"
                    }
                    value={vehicle[k]}
                    onChange={(e) =>
                      setVehicle({ ...vehicle, [k]: e.target.value })
                    }
                  />
                </label>
              ))}
            <button className="brand-btn rounded-xl px-4 py-2 font-bold text-white md:col-span-4">
              {t("checkpointD.actions.save")}
            </button>
          </form>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {vehicles.map((v) => (
              <div className="rounded-xl border p-3" key={v.id}>
                <strong>{v.registration_number}</strong> · {v.vehicle_type}
                <p>
                  {v.driver_name || t("checkpointD.values.missing")} ·{" "}
                  {v.max_payload_kg} kg
                </p>
                <p>
                  {v.internal_length_mm} × {v.internal_width_mm} ×{" "}
                  {v.internal_height_mm} mm ·{" "}
                  {v.max_volume_m3 ?? t("checkpointD.values.missing")} m³
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      <form
        className={`${panel} grid gap-3 md:grid-cols-3`}
        onSubmit={createTrip}
      >
        <h2 className="font-black md:col-span-3">
          {t("checkpointD.trips.create")}
        </h2>
        <input
          className={field}
          required
          placeholder={t("checkpointD.fields.trip_number")}
          value={trip.trip_number}
          onChange={(e) => setTrip({ ...trip, trip_number: e.target.value })}
        />
        <select
          className={field}
          required
          value={trip.project_id}
          onChange={(e) => {
            setTrip({
              ...trip,
              project_id: e.target.value,
              release_id: "",
            });
          }}
        >
          <option value="">{t("checkpointD.fields.project")}</option>
          {projects
            .filter((p) => p.release_revision > 0)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.project_code} · {p.destination_city}
              </option>
            ))}
        </select>
        <select className={field} required value={trip.driver_user_id} onChange={(e) => setTrip({ ...trip, driver_user_id: e.target.value })}>
          <option value="">{t("checkpointD.fields.driver_name")}</option>
          {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.username}</option>)}
        </select>
        <select
          className={field}
          required
          value={trip.vehicle_id}
          onChange={(e) => setTrip({ ...trip, vehicle_id: e.target.value })}
        >
          <option value="">{t("checkpointD.fields.vehicle")}</option>
          {vehicles
            .filter((v) => v.is_active)
            .map((v) => (
              <option key={v.id} value={v.id}>
                {v.registration_number}
              </option>
            ))}
        </select>
        <input
          className={field}
          type="datetime-local"
          value={trip.planned_departure_at}
          onChange={(e) =>
            setTrip({ ...trip, planned_departure_at: e.target.value })
          }
        />
        <select
          className={field}
          value={trip.evidence_policy}
          onChange={(e) =>
            setTrip({ ...trip, evidence_policy: e.target.value })
          }
        >
          <option value="required">{t("checkpointD.policy.required")}</option>
          <option value="optional">{t("checkpointD.policy.optional")}</option>
        </select>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={trip.completeness_required}
            onChange={(e) =>
              setTrip({ ...trip, completeness_required: e.target.checked })
            }
          />
          {t("checkpointD.policy.completeShipment")}
        </label>
        <button className="brand-btn rounded-xl px-4 py-2 font-bold text-white md:col-span-3">
          {t("checkpointD.actions.create")}
        </button>
      </form>
      <div className="grid gap-3">
        {trips.map((x) => (
          <Link
            className={panel}
            to={`/mes/finished-logistics/trips/${x.id}`}
            key={x.id}
          >
            <div className="flex flex-wrap justify-between gap-2">
              <strong>{x.trip_number}</strong>
              <span>{t(`checkpointD.status.${x.status}`)}</span>
            </div>
            <p>
              {x.destination_city} ·{" "}
              {x.driver_name_snapshot || t("checkpointD.values.missing")}
            </p>
            <p className="text-sm text-[var(--brand-muted)]">
              {date(x.planned_departure_at, locale)} ·{" "}
              {number(x.known_total_weight, locale)} kg
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}
