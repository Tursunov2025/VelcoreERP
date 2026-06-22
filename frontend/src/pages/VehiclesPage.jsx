import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const emptyForm = { plate_number: "", model: "", status: "active" };

export default function VehiclesPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("export_manage");

  const [vehicles, setVehicles] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm });

  const load = useCallback(async () => {
    setError("");
    try {
      const [v, s] = await Promise.all([
        api.gpsVehicles(),
        api.gpsTransportSuggestions().catch(() => ({ suggestions: [] })),
      ]);
      setVehicles(v.vehicles || []);
      setSuggestions(s.suggestions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const createVehicle = async (e) => {
    e.preventDefault();
    if (!form.plate_number.trim()) return;
    try {
      await api.gpsCreateVehicle({
        plate_number: form.plate_number.trim(),
        model: form.model.trim(),
        status: form.status,
      });
      setToast("Vehicle created");
      setForm({ ...emptyForm });
      setShowForm(false);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const importFromTransports = async () => {
    try {
      const res = await api.gpsImportFromTransports();
      setToast(
        `Imported ${res.vehicles_created} vehicles, ${res.drivers_created} drivers from transports`
      );
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const applySuggestion = (s) => {
    setForm({
      plate_number: s.plate_number,
      model: s.model || "",
      status: "active",
    });
    setShowForm(true);
  };

  return (
    <div className="pb-24">
      <BackButton fallback="/gps" label="GPS Monitoring" className="mb-4" />
      <PageHeader
        title="Fleet Vehicles"
        subtitle="GPS-tracked trucks linked to transport shipments"
        actions={
          canManage ? (
            <div className="flex flex-wrap gap-2">
              {suggestions.length > 0 ? (
                <button
                  type="button"
                  onClick={importFromTransports}
                  className="rounded-xl border px-4 py-2.5 text-sm font-bold"
                >
                  Import from Transports ({suggestions.length})
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setShowForm((v) => !v)}
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                + Create Vehicle
              </button>
            </div>
          ) : null
        }
      />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {suggestions.length > 0 ? (
        <div className="mb-4 rounded-3xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <p className="mb-2 text-sm font-bold text-amber-900 dark:text-amber-200">
            Suggested from existing transports (not yet in GPS fleet)
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s.transport_id}
                type="button"
                onClick={() => applySuggestion(s)}
                className="rounded-xl border bg-white px-3 py-2 text-left text-sm dark:bg-[var(--brand-card)]"
              >
                <span className="font-mono font-bold">{s.plate_number}</span>
                {s.driver_name ? (
                  <span className="ml-2 text-[var(--brand-muted)]">· {s.driver_name}</span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {showForm && canManage ? (
        <form
          onSubmit={createVehicle}
          className="mb-6 grid gap-2 rounded-3xl border bg-[var(--brand-card)] p-4 sm:grid-cols-4"
        >
          <input
            value={form.plate_number}
            onChange={(e) => setForm({ ...form, plate_number: e.target.value })}
            placeholder="Plate number (e.g. 01 A 777 AA)"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
            required
          />
          <input
            value={form.model}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
            placeholder="Model (KamAZ, Volvo...)"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="maintenance">Maintenance</option>
          </select>
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Save Vehicle
          </button>
        </form>
      ) : null}

      <div className="space-y-2">
        {vehicles.map((v) => (
          <div key={v.id} className="rounded-2xl border bg-[var(--brand-card)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-mono text-lg font-black">{v.plate_number}</p>
                <p className="text-sm text-[var(--brand-muted)]">{v.model || "No model"}</p>
              </div>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold capitalize dark:bg-gray-800">
                {v.status}
              </span>
            </div>
            {v.latest_location ? (
              <p className="mt-2 text-xs text-[var(--brand-muted)]">
                Last GPS: {v.latest_location.latitude?.toFixed(4)},{" "}
                {v.latest_location.longitude?.toFixed(4)} ·{" "}
                {v.latest_location.online ? (
                  <span className="text-green-600">Online</span>
                ) : (
                  <span>Offline</span>
                )}
              </p>
            ) : (
              <p className="mt-2 text-xs text-[var(--brand-muted)]">No GPS data yet</p>
            )}
          </div>
        ))}
        {!loading && vehicles.length === 0 ? (
          <div className="rounded-3xl border bg-[var(--brand-card)] p-8 text-center">
            <p className="text-[var(--brand-muted)]">No vehicles registered for GPS tracking.</p>
            {canManage ? (
              <button
                type="button"
                onClick={importFromTransports}
                className="mt-4 rounded-xl px-4 py-2 text-sm font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                Import from Transports
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Link to="/transport/drivers" className="font-semibold text-blue-600 hover:underline">
          Manage Drivers →
        </Link>
        <Link to="/driver-tracking" className="font-semibold text-blue-600 hover:underline">
          Driver GPS Tracking →
        </Link>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
