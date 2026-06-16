import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import FleetMap from "../components/gps/FleetMap";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function LiveMapPage() {
  const [locations, setLocations] = useState([]);
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [route, setRoute] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api.gpsLatestLocations();
      setLocations(data.locations || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
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
        subtitle="Real-time truck locations (OpenStreetMap)"
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
                className={`h-2.5 w-2.5 rounded-full ${loc.online ? "bg-green-500" : "bg-gray-400"}`}
              />
            </div>
            <p className="text-sm text-[var(--brand-muted)]">{loc.driver_name || "No driver"}</p>
            <p className="mt-1 text-xs text-[var(--brand-muted)]">
              {loc.speed ?? 0} km/h ·{" "}
              {loc.recorded_at ? new Date(loc.recorded_at).toLocaleString() : "—"}
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
