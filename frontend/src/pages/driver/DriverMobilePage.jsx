import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useBranding } from "../../context/BrandingContext";
import { useUsers } from "../../hooks/useUsers";

const UPDATE_INTERVAL_MS = 5_000;

function DriverLoginForm() {
  const { login, loginError, isSubmitting } = useAuth();
  const { branding } = useBranding();
  const { users, loading, error } = useUsers({ enabled: true, forLogin: true });
  const [loginUser, setLoginUser] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    await login(loginUser, loginPassword);
  };

  return (
    <div
      className="flex min-h-screen flex-col justify-center p-4"
      style={{ backgroundColor: "var(--brand-background)" }}
    >
      <div className="mx-auto w-full max-w-md rounded-3xl border bg-[var(--brand-card)] p-6 shadow-lg">
        <h1 className="text-center text-2xl font-black text-[var(--brand-text)]">
          {branding.app_name || "Velcore"}
        </h1>
        <p className="mb-6 text-center text-sm text-[var(--brand-muted)]">
          Haydovchi GPS — login
        </p>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <select
            value={loginUser}
            onChange={(e) => setLoginUser(e.target.value)}
            disabled={loading}
            className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm"
            required
          >
            <option value="">{loading ? "Yuklanmoqda…" : "Foydalanuvchi"}</option>
            {users.map((user) => (
              <option key={user.username} value={user.username}>
                {user.username}
              </option>
            ))}
          </select>
          {error ? <p className="text-sm text-red-500">{error}</p> : null}
          <input
            type="password"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            placeholder="Parol"
            className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm"
            required
          />
          {loginError ? <p className="text-sm text-red-500">{loginError}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-xl py-3 font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {isSubmitting ? "…" : "Kirish"}
          </button>
        </form>
      </div>
    </div>
  );
}

function DriverTrackingPanel() {
  const { username, logout } = useAuth();
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
      await api.gpsUpdate({
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
    } catch (e) {
      setToast(e.message);
    } finally {
      sendingRef.current = false;
    }
  }, [vehicleId, driverId, battery, pageActive]);

  const startTracking = () => {
    if (!vehicleId) {
      setToast("Avval mashina tanlang");
      return;
    }
    if (!navigator.geolocation) {
      setToast("Geolocation qo'llab-quvvatlanmaydi");
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

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen pb-8"
      style={{ backgroundColor: "var(--brand-background)" }}
    >
      <div className="border-b bg-[var(--brand-card)] px-4 py-4">
        <div className="mx-auto flex max-w-lg items-center justify-between">
          <div>
            <p className="text-xs text-[var(--brand-muted)]">Haydovchi GPS</p>
            <p className="font-bold text-[var(--brand-text)]">{username}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              stopTracking();
              logout();
            }}
            className="text-sm font-semibold text-red-600"
          >
            Chiqish
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-lg space-y-4 p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
            <p className="text-xs uppercase text-[var(--brand-muted)]">Holat</p>
            <p className={`font-bold ${tracking && pageActive ? "text-green-600" : "text-gray-500"}`}>
              {tracking && pageActive ? "Live" : tracking ? "Pauza" : "O&apos;chiq"}
            </p>
          </div>
          <div className="rounded-2xl border bg-[var(--brand-card)] p-3">
            <p className="text-xs uppercase text-[var(--brand-muted)]">Yuborilgan</p>
            <p className="font-bold">{sendCount}</p>
          </div>
        </div>

        <div className="space-y-3 rounded-3xl border bg-[var(--brand-card)] p-4">
          <select
            value={vehicleId}
            onChange={(e) => setVehicleId(e.target.value)}
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
            disabled={tracking}
          >
            <option value="">Mashina tanlang *</option>
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
            <option value="">Haydovchi (ixtiyoriy)</option>
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name}
              </option>
            ))}
          </select>
          {coords ? (
            <p className="text-xs text-[var(--brand-muted)]">
              📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)}
              {lastSent ? ` · ${lastSent.toLocaleTimeString()}` : ""}
            </p>
          ) : null}
          {!tracking ? (
            <button
              type="button"
              onClick={startTracking}
              className="w-full rounded-xl py-4 text-lg font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              Kuzatuvni boshlash
            </button>
          ) : (
            <button
              type="button"
              onClick={stopTracking}
              className="w-full rounded-xl bg-red-600 py-4 text-lg font-bold text-white"
            >
              To&apos;xtatish
            </button>
          )}
          <p className="text-center text-xs text-[var(--brand-muted)]">
            GPS har {UPDATE_INTERVAL_MS / 1000} soniyada serverga yuboriladi
          </p>
        </div>

        <ErrorAlert message={error} />
        <Toast message={toast} onClose={() => setToast("")} />
      </div>
    </div>
  );
}

export default function DriverMobilePage() {
  const { isLoggedIn, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!isLoggedIn) {
    return <DriverLoginForm />;
  }

  return <DriverTrackingPanel />;
}
