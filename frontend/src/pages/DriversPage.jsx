import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const emptyForm = {
  full_name: "",
  phone: "",
  telegram_username: "",
  status: "active",
};

export default function DriversPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("export_manage");

  const [drivers, setDrivers] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm });

  const load = useCallback(async () => {
    setError("");
    try {
      const [d, s] = await Promise.all([
        api.gpsDrivers(),
        api.gpsTransportSuggestions().catch(() => ({ suggestions: [] })),
      ]);
      setDrivers(d.drivers || []);
      setSuggestions(
        (s.suggestions || []).filter((x) => x.driver_name && !x.driver_exists)
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const createDriver = async (e) => {
    e.preventDefault();
    if (!form.full_name.trim()) return;
    try {
      await api.gpsCreateDriver({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        telegram_username: form.telegram_username.trim(),
        status: form.status,
      });
      setToast("Driver created");
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
        `Imported ${res.vehicles_created} vehicles, ${res.drivers_created} drivers`
      );
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const applySuggestion = (s) => {
    setForm({
      full_name: s.driver_name,
      phone: s.driver_phone || "",
      telegram_username: "",
      status: "active",
    });
    setShowForm(true);
  };

  return (
    <div className="pb-24">
      <BackButton fallback="/transport" label="Transport" className="mb-4" />
      <PageHeader
        title="Fleet Drivers"
        subtitle="Drivers linked to GPS vehicle tracking"
        actions={
          canManage ? (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowForm((v) => !v)}
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                + Create Driver
              </button>
            </div>
          ) : null
        }
      />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {suggestions.length > 0 ? (
        <div className="mb-4 rounded-3xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950/30">
          <p className="mb-2 text-sm font-bold text-blue-900 dark:text-blue-200">
            Suggested from transport records
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={`${s.transport_id}-${s.driver_name}`}
                type="button"
                onClick={() => applySuggestion(s)}
                className="rounded-xl border bg-white px-3 py-2 text-sm dark:bg-[var(--brand-card)]"
              >
                <span className="font-bold">{s.driver_name}</span>
                {s.driver_phone ? (
                  <span className="ml-2 text-[var(--brand-muted)]">{s.driver_phone}</span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {showForm && canManage ? (
        <form
          onSubmit={createDriver}
          className="mb-6 grid gap-2 rounded-3xl border bg-[var(--brand-card)] p-4 sm:grid-cols-2 lg:grid-cols-5"
        >
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Full name"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
            required
          />
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="Phone"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <input
            value={form.telegram_username}
            onChange={(e) => setForm({ ...form, telegram_username: e.target.value })}
            placeholder="Telegram @username"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="on_trip">On trip</option>
          </select>
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Save Driver
          </button>
        </form>
      ) : null}

      <div className="space-y-2">
        {drivers.map((d) => (
          <div key={d.id} className="rounded-2xl border bg-[var(--brand-card)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-lg font-bold">{d.full_name}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {d.phone || "—"}
                  {d.telegram_username ? ` · @${d.telegram_username}` : ""}
                </p>
              </div>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold capitalize dark:bg-gray-800">
                {d.status}
              </span>
            </div>
          </div>
        ))}
        {!loading && drivers.length === 0 ? (
          <div className="rounded-3xl border bg-[var(--brand-card)] p-8 text-center">
            <p className="text-[var(--brand-muted)]">No drivers registered.</p>
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
        <Link to="/transport/vehicles" className="font-semibold text-blue-600 hover:underline">
          ← Manage Vehicles
        </Link>
        <Link to="/driver-tracking" className="font-semibold text-blue-600 hover:underline">
          Driver GPS Tracking →
        </Link>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
