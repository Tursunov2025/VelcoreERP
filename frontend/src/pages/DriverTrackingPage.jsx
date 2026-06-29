import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const UPDATE_INTERVAL_MS = 5_000;

export default function DriverTrackingPage() {
  const { username } = useAuth();
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [vehicleId, setVehicleId] = useState("");
  const [driverId, setDriverId] = useState("");
  const [tracking, setTracking] = useState(false);
  const [pageActive, setPageActive] = useState(!document.hidden);
  const [lastSent, setLastSent] = useState(null);
  const [coords, setCoords] = useState(null);
  const [battery, setBattery] = useState(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [sendCount, setSendCount] = useState(0);
  const watchIdRef = useRef(null);
  const intervalRef = useRef(null);
  const latestPosRef = useRef(null);
  const sendingRef = useRef(false);

  const loadMeta = useCallback(async () => {
    setError("");
    try {
      const [v, d] = await Promise.all([api.gpsVehicles(), api.gpsDrivers()]);
      setVehicles(v.vehicles || []);
      setDrivers(d.drivers || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMeta();
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    const onVisibility = () => setPageActive(!document.hidden);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [loadMeta]);

  useEffect(() => {
    if (navigator.getBattery) {
      navigator
        .getBattery()
        .then((b) => {
          setBattery(Math.round(b.level * 100));
          b.addEventListener("levelchange", () => setBattery(Math.round(b.level * 100)));
        })
        .catch(() => {});
    }
  }, []);

  const sendLocation = useCallback(async () => {
    const pos = latestPosRef.current;
    if (!pos || !vehicleId || sendingRef.current) return;
    if (!pageActive || !navigator.onLine) return;

    sendingRef.current = true;
    try {
      const result = await api.gpsUpdateLocation({
        vehicle_id: Number(vehicleId),
        driver_id: driverId ? Number(driverId) : null,
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        speed: pos.coords.speed != null ? Math.max(0, pos.coords.speed * 3.6) : 0,
        battery_level: battery,
      });
      setLastSent(new Date());
      setSendCount((c) => c + 1);
      setCoords({
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
      });
      if (result.duplicate_skipped) {
        setToast("");
      }
    } catch (e) {
      setToast(e.message);
    } finally {
      sendingRef.current = false;
    }
  }, [vehicleId, driverId, battery, pageActive]);

  const startTracking = () => {
    if (!vehicleId) {
      setToast("Select a vehicle first");
      return;
    }
    if (!navigator.geolocation) {
      setToast("Geolocation not supported");
      return;
    }
    setTracking(true);
    setError("");
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        latestPosRef.current = pos;
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
      },
      (err) => setError(err.message),
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 15_000 }
    );
    sendLocation();
    intervalRef.current = setInterval(sendLocation, UPDATE_INTERVAL_MS);
  };

  const stopTracking = () => {
    setTracking(false);
    if (watchIdRef.current != null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => () => stopTracking(), []);

  return (
    <div className="pb-28">
      <BackButton fallback="/logistics/live-map" label="Live Map" className="mb-4" />
      <PageHeader
        title="Driver GPS Tracking"
        subtitle={`Live updates every 5s · ${username}${pageActive ? "" : " · paused (tab hidden)"}`}
      />

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Status</p>
          <p className={`font-bold ${tracking && pageActive ? "text-green-600" : "text-gray-500"}`}>
            {tracking && pageActive ? "Live tracking" : tracking ? "Paused" : "Offline"}
          </p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Network</p>
          <p className={`font-bold ${online ? "text-green-600" : "text-red-500"}`}>
            {online ? "Online" : "Offline"}
          </p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Battery</p>
          <p className="font-bold">{battery != null ? `${battery}%` : "—"}</p>
        </div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Last sent</p>
          <p className="text-sm font-bold">
            {lastSent ? lastSent.toLocaleTimeString() : "—"}
            {sendCount > 0 ? ` (${sendCount})` : ""}
          </p>
        </div>
      </div>

      <div className="mb-4 space-y-3 rounded-3xl border bg-[var(--brand-card)] p-4">
        {(vehicles.length === 0 || drivers.length === 0) && !loading ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/30">
            <p className="font-semibold text-amber-900 dark:text-amber-200">
              {vehicles.length === 0 && drivers.length === 0
                ? "No fleet vehicles or drivers registered yet."
                : vehicles.length === 0
                  ? "No vehicles registered — select or create one first."
                  : "No drivers registered — optional but recommended."}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {vehicles.length === 0 ? (
                <Link
                  to="/logistics/transports"
                  className="rounded-lg px-3 py-1.5 text-xs font-bold text-white"
                  style={{ backgroundColor: "var(--brand-button)" }}
                >
                  + Create Vehicle
                </Link>
              ) : null}
              {drivers.length === 0 ? (
                <Link
                  to="/logistics/drivers"
                  className="rounded-lg border px-3 py-1.5 text-xs font-bold"
                >
                  + Create Driver
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
        <select
          value={vehicleId}
          onChange={(e) => setVehicleId(e.target.value)}
          className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
          disabled={tracking}
        >
          <option value="">Select vehicle</option>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.plate_number} {v.model ? `· ${v.model}` : ""}
            </option>
          ))}
        </select>
        <select
          value={driverId}
          onChange={(e) => setDriverId(e.target.value)}
          className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
          disabled={tracking}
        >
          <option value="">Select driver (optional)</option>
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>
              {d.full_name}
            </option>
          ))}
        </select>
        {coords ? (
          <p className="text-xs text-[var(--brand-muted)]">
            📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±{Math.round(coords.accuracy)}m)
          </p>
        ) : null}
        <div className="flex gap-2">
          {!tracking ? (
            <button
              type="button"
              onClick={startTracking}
              className="flex-1 rounded-xl py-3 font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              Start live GPS
            </button>
          ) : (
            <button
              type="button"
              onClick={stopTracking}
              className="flex-1 rounded-xl bg-red-600 py-3 font-bold text-white"
            >
              Stop tracking
            </button>
          )}
        </div>
      </div>

      <ErrorAlert message={error} />
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
