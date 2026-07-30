import { useCallback, useEffect, useRef, useState } from "react";
import {
  enqueueLocation,
  getApiBase,
  getSettings,
  getStoredTokens,
  login,
  postLocation,
  saveSettings,
  syncOfflineQueue,
} from "../api/client";

const WEB_INTERVAL_MS = 5000;

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isProd = import.meta.env.PROD;

  useEffect(() => {
    getSettings().then((s) => setApiUrl(s.apiUrl || getApiBase()));
    getStoredTokens().then((t) => {
      if (t?.access_token) onLoggedIn(t);
    });
  }, [onLoggedIn]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (!isProd) await saveSettings({ apiUrl: apiUrl.trim() || getApiBase() });
      const user = await login(username.trim(), password);
      onLoggedIn(user);
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="logo">
        <h1>Velcore Driver</h1>
        <p>Velcore ERP — haydovchi GPS kuzatuvi</p>
      </div>
      {error ? <div className="error">{error}</div> : null}
      <form onSubmit={submit} className="card">
        {isProd ? (
          <div className="field">
            <label>Server</label>
            <input value={getApiBase()} readOnly disabled />
          </div>
        ) : (
          <div className="field">
            <label>Server URL</label>
            <input
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://api.velcore.uz"
              autoComplete="off"
            />
          </div>
        )}
        <div className="field">
          <label>Username</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

/** Browser fallback when not running as native APK */
export function useWebGpsTracking(active, vehicleId, driverId, onStatus) {
  const watchRef = useRef(null);
  const intervalRef = useRef(null);
  const posRef = useRef(null);

  useEffect(() => {
    if (!active || !vehicleId) return undefined;

    const send = async () => {
      const pos = posRef.current;
      if (!pos) return;
      const payload = {
        vehicle_id: Number(vehicleId),
        driver_id: driverId ? Number(driverId) : null,
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        speed: pos.coords.speed != null ? Math.max(0, pos.coords.speed * 3.6) : 0,
        battery_level: null,
      };
      try {
        await postLocation(payload);
        onStatus?.({ lastSent: new Date().toISOString(), queued: 0, accuracy: pos.coords.accuracy });
      } catch {
        await enqueueLocation(payload);
        const q = await syncOfflineQueue().catch(() => ({ remaining: 0 }));
        onStatus?.({ lastSent: null, queued: q.remaining, accuracy: pos.coords.accuracy });
      }
    };

    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        posRef.current = pos;
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    send();
    intervalRef.current = setInterval(send, WEB_INTERVAL_MS);

    return () => {
      if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [active, vehicleId, driverId, onStatus]);
}
