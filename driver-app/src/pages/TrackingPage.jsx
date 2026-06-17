import { useCallback, useEffect, useState } from "react";
import { App } from "@capacitor/app";
import { Network } from "@capacitor/network";
import {
  fetchDrivers,
  fetchVehicles,
  getSettings,
  getStoredTokens,
  logout,
  syncOfflineQueue,
} from "../api/client";
import { DriverTracking, isNativeAndroid } from "../plugins/driverTracking";
import { useWebGpsTracking } from "./LoginPage";

function qualityLabel(accuracy) {
  if (accuracy == null) return "—";
  if (accuracy <= 10) return "Excellent";
  if (accuracy <= 30) return "Good";
  if (accuracy <= 80) return "Fair";
  return "Poor";
}

export default function TrackingPage({ user, onLogout }) {
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [vehicleId, setVehicleId] = useState("");
  const [driverId, setDriverId] = useState("");
  const [tripping, setTripping] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(true);
  const [status, setStatus] = useState({
    lastSent: null,
    accuracy: null,
    battery: null,
    speed: 0,
    queued: 0,
    latitude: null,
    longitude: null,
  });

  const loadMeta = useCallback(async () => {
    setError("");
    try {
      const [v, d] = await Promise.all([fetchVehicles(), fetchDrivers()]);
      setVehicles(v);
      setDrivers(d);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    Network.getStatus().then((s) => setOnline(s.connected));
    const h = Network.addListener("networkStatusChange", (s) => {
      setOnline(s.connected);
      if (s.connected) syncOfflineQueue().then((r) => setStatus((st) => ({ ...st, queued: r.remaining })));
    });
    return () => {
      h.then((l) => l.remove());
    };
  }, []);

  const onNativeStatus = useCallback((event) => {
    const d = event?.detail || event;
    setStatus((st) => ({
      ...st,
      lastSent: d.lastSent || st.lastSent,
      accuracy: d.accuracy ?? st.accuracy,
      battery: d.battery ?? st.battery,
      speed: d.speed ?? st.speed,
      queued: d.queued ?? st.queued,
      latitude: d.latitude ?? st.latitude,
      longitude: d.longitude ?? st.longitude,
    }));
  }, []);

  useEffect(() => {
    if (!isNativeAndroid()) return undefined;
    const listener = DriverTracking.addListener("status", onNativeStatus);
    DriverTracking.getStatus?.().then(onNativeStatus).catch(() => {});
    return () => {
      listener.then((l) => l.remove());
    };
  }, [onNativeStatus]);

  const onWebStatus = useCallback((s) => {
    setStatus((st) => ({
      ...st,
      lastSent: s.lastSent || st.lastSent,
      accuracy: s.accuracy ?? st.accuracy,
      queued: s.queued ?? st.queued,
    }));
  }, []);

  useWebGpsTracking(!isNativeAndroid() && tripping, vehicleId, driverId, onWebStatus);

  const startTrip = async () => {
    if (!vehicleId) {
      setError("Select a vehicle");
      return;
    }
    setError("");
    const settings = await getSettings();
    const tokens = await getStoredTokens();
    const vehicle = vehicles.find((v) => String(v.id) === String(vehicleId));
    const driver = drivers.find((d) => String(d.id) === String(driverId));

    if (isNativeAndroid()) {
      try {
        await DriverTracking.startTrip({
          apiUrl: settings.apiUrl,
          token: tokens.access_token,
          vehicleId: Number(vehicleId),
          driverId: driverId ? Number(driverId) : null,
          plateNumber: vehicle?.plate_number || "",
          driverName: driver?.full_name || user.username,
        });
        setTripping(true);
      } catch (e) {
        setError(e.message || "Failed to start trip");
      }
    } else {
      setTripping(true);
    }
  };

  const stopTrip = async () => {
    if (isNativeAndroid()) {
      try {
        await DriverTracking.stopTrip();
      } catch {
        /* ignore */
      }
    }
    setTripping(false);
    await syncOfflineQueue();
  };

  useEffect(() => {
    const sub = App.addListener("appStateChange", ({ isActive }) => {
      if (isActive && tripping) {
        syncOfflineQueue().then((r) => setStatus((st) => ({ ...st, queued: r.remaining })));
        if (isNativeAndroid()) DriverTracking.getStatus?.().then(onNativeStatus).catch(() => {});
      }
    });
    return () => {
      sub.then((s) => s.remove());
    };
  }, [tripping, onNativeStatus]);

  const handleLogout = async () => {
    if (tripping) await stopTrip();
    await logout();
    onLogout();
  };

  const selectedVehicle = vehicles.find((v) => String(v.id) === String(vehicleId));
  const selectedDriver = drivers.find((d) => String(d.id) === String(driverId));

  return (
    <div className="app-shell">
      <div className="logo">
        <h1>Azmus Driver</h1>
        <p>
          {user.username}{" "}
          <span className={`badge ${tripping ? "badge-live" : "badge-off"}`}>
            {tripping ? "TRIP ACTIVE" : "IDLE"}
          </span>
        </p>
      </div>

      {error ? <div className="error">{error}</div> : null}

      {!tripping ? (
        <div className="card">
          <h2>Vehicle</h2>
          <div className="field">
            <label>Select vehicle</label>
            <select value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
              <option value="">—</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate_number} {v.model ? `· ${v.model}` : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Driver (optional)</label>
            <select value={driverId} onChange={(e) => setDriverId(e.target.value)}>
              <option value="">—</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="btn btn-primary" onClick={startTrip}>
            Start Trip
          </button>
        </div>
      ) : (
        <div className="card">
          <h2>Trip in progress</h2>
          <p className="muted">GPS every 5s · foreground service on Android</p>
          <button type="button" className="btn btn-danger" onClick={stopTrip} style={{ marginTop: "0.75rem" }}>
            Stop Trip
          </button>
        </div>
      )}

      <div className="card">
        <h2>Status</h2>
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-label">Vehicle</div>
            <div className="stat-value">{selectedVehicle?.plate_number || "—"}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Driver</div>
            <div className="stat-value">{selectedDriver?.full_name || user.username}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Last sent</div>
            <div className="stat-value">
              {status.lastSent ? new Date(status.lastSent).toLocaleTimeString() : "—"}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">GPS quality</div>
            <div className="stat-value">{qualityLabel(status.accuracy)}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Battery</div>
            <div className="stat-value">
              {status.battery != null ? `${Math.round(status.battery)}%` : "—"}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">Network</div>
            <div className="stat-value">{online ? "Online" : "Offline"}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Speed</div>
            <div className="stat-value">{Math.round(status.speed || 0)} km/h</div>
          </div>
          <div className="stat">
            <div className="stat-label">Queued</div>
            <div className="stat-value">{status.queued || 0}</div>
          </div>
        </div>
        {status.latitude != null ? (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            📍 {status.latitude.toFixed(5)}, {status.longitude?.toFixed(5)}
            {status.accuracy != null ? ` (±${Math.round(status.accuracy)}m)` : ""}
          </p>
        ) : null}
      </div>

      <button type="button" className="btn" style={{ background: "#334155", color: "#fff" }} onClick={handleLogout}>
        Sign out
      </button>
    </div>
  );
}
