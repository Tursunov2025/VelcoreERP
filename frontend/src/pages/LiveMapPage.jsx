import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import FleetMap, { formatGpsAge } from "../components/gps/FleetMap";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

const REFRESH_MS = 5_000;

export default function LiveMapPage() {
  const [locations, setLocations] = useState([]);
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [route, setRoute] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.gpsLatestLocations();
      setLocations(data.locations || []);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const selectVehicle = async (vehicleId) => {
    setSelectedVehicle(vehicleId);
    try {
      const hist = await api.gpsLocationHistory(vehicleId, 80);
      setRoute(hist.history || []);
    } catch {
      setRoute([]);
    }
  };

  return (
    <div className="pb-24">
      <BackButton fallback="/transport" label="Transport" className="mb-4" />
      <PageHeader
        title="Live Fleet Map"
        subtitle={
          lastRefresh
            ? `Auto-refresh every 5s · updated ${lastRefresh.toLocaleTimeString()}`
            : "Real-time truck locations (OpenStreetMap)"
        }
        actions={
          <Link
            to="/driver-tracking"
            className="rounded-xl px-4 py-2 text-sm font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Driver GPS
          </Link>
        }
      />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <FleetMap markers={locations} route={route} height="min(60vh, 520px)" className="mb-4" />

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {locations.map((loc) => (
          <button
            key={loc.vehicle_id}
            type="button"
            onClick={() => selectVehicle(loc.vehicle_id)}
            className={`rounded-2xl border bg-[var(--brand-card)] p-4 text-left transition hover:shadow-md ${
              selectedVehicle === loc.vehicle_id ? "ring-2 ring-[var(--brand-button)]" : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <p className="font-mono font-bold text-[var(--brand-text)]">{loc.plate_number}</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                  loc.online
                    ? loc.moving
                      ? "bg-green-100 text-green-700"
                      : "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {loc.online ? (loc.moving ? "Moving" : "Online") : "Offline"}
              </span>
            </div>
            <p className="text-sm text-[var(--brand-muted)]">{loc.driver_name || "No driver"}</p>
            <p className="mt-1 text-xs text-[var(--brand-muted)]">
              {Math.round(loc.speed ?? 0)} km/h · 🔋{" "}
              {loc.battery_level != null ? `${Math.round(loc.battery_level)}%` : "—"} ·{" "}
              {formatGpsAge(loc.seconds_since_update)}
            </p>
          </button>
        ))}
        {!loading && locations.length === 0 ? (
          <p className="col-span-full py-8 text-center text-sm text-[var(--brand-muted)]">
            No GPS locations yet. Add vehicles and use Driver Tracking to share location.
          </p>
        ) : null}
      </div>
    </div>
  );
}
