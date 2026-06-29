import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";

const emptyForm = {
  title: "",
  description: "",
  vehicle_id: "",
  driver_id: "",
  origin: "",
  destination: "",
  status: "assigned",
};

const STATUS_LABELS = {
  assigned: "Tayinlangan",
  active: "Faol",
  completed: "Yakunlangan",
  cancelled: "Bekor",
};

export default function TransportTasksPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("export_manage");
  const canView = isAdmin || hasPermission("export_view");

  const [tasks, setTasks] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm });

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const [t, v, d] = await Promise.all([
        api.gpsTransportTasks(),
        api.gpsVehicles(),
        api.gpsDrivers(),
      ]);
      setTasks(t.tasks || []);
      setVehicles(v.vehicles || []);
      setDrivers(d.drivers || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const createTask = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    try {
      await api.gpsCreateTransportTask({
        title: form.title.trim(),
        description: form.description.trim(),
        vehicle_id: form.vehicle_id ? Number(form.vehicle_id) : null,
        driver_id: form.driver_id ? Number(form.driver_id) : null,
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        status: form.status,
      });
      setToast("Vazifa yaratildi");
      setForm({ ...emptyForm });
      setShowForm(false);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const toggleTracking = async (task, start) => {
    try {
      if (start) {
        await api.gpsStartTransportTask(task.id);
        setToast("Kuzatuv boshlandi");
      } else {
        await api.gpsStopTransportTask(task.id);
        setToast("Kuzatuv to'xtatildi");
      }
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  if (!canView) {
    return <p className="py-12 text-center text-red-500">Ruxsat yo&apos;q</p>;
  }

  return (
    <div className="pb-24">
      <BackButton fallback="/gps" label="GPS Monitoring" className="mb-4" />
      <PageHeader
        title="Transport vazifalari"
        subtitle="Mashina + haydovchi + marshrut vazifalari"
        actions={
          canManage ? (
            <button
              type="button"
              onClick={() => setShowForm((v) => !v)}
              className="rounded-xl px-4 py-2 text-sm font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              + Vazifa
            </button>
          ) : null
        }
      />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {showForm && canManage ? (
        <form
          onSubmit={createTask}
          className="mb-6 space-y-3 rounded-3xl border bg-[var(--brand-card)] p-4"
        >
          <input
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="Vazifa nomi *"
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
            required
          />
          <textarea
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Tavsif"
            rows={2}
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={form.vehicle_id}
              onChange={(e) => setForm((f) => ({ ...f, vehicle_id: e.target.value }))}
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            >
              <option value="">Mashina</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate_number}
                </option>
              ))}
            </select>
            <select
              value={form.driver_id}
              onChange={(e) => setForm((f) => ({ ...f, driver_id: e.target.value }))}
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            >
              <option value="">Haydovchi</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={form.origin}
              onChange={(e) => setForm((f) => ({ ...f, origin: e.target.value }))}
              placeholder="Qayerdan"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />
            <input
              value={form.destination}
              onChange={(e) => setForm((f) => ({ ...f, destination: e.target.value }))}
              placeholder="Qayerga"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-xl py-3 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Saqlash
          </button>
        </form>
      ) : null}

      <div className="space-y-3">
        {tasks.map((task) => (
          <div
            key={task.id}
            className="rounded-2xl border bg-[var(--brand-card)] p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-bold text-[var(--brand-text)]">{task.title}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {task.vehicle_plate || "—"} · {task.driver_name || "—"}
                </p>
                <p className="text-xs text-[var(--brand-muted)]">
                  {task.origin || "—"} → {task.destination || "—"}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                  task.tracking_active
                    ? "bg-green-100 text-green-700"
                    : task.status === "completed"
                      ? "bg-gray-100 text-gray-600"
                      : "bg-blue-100 text-blue-700"
                }`}
              >
                {task.tracking_active ? "Live" : STATUS_LABELS[task.status] || task.status}
              </span>
            </div>
            {task.latest_location?.online ? (
              <p className="mt-2 text-xs text-green-600">
                GPS online · {Math.round(task.latest_location.speed ?? 0)} km/h
              </p>
            ) : null}
            {canManage && task.vehicle_id ? (
              <div className="mt-3 flex gap-2">
                {!task.tracking_active && task.status !== "completed" ? (
                  <button
                    type="button"
                    onClick={() => toggleTracking(task, true)}
                    className="rounded-lg px-3 py-1.5 text-xs font-bold text-white"
                    style={{ backgroundColor: "var(--brand-button)" }}
                  >
                    Kuzatuvni boshlash
                  </button>
                ) : task.tracking_active ? (
                  <button
                    type="button"
                    onClick={() => toggleTracking(task, false)}
                    className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white"
                  >
                    To&apos;xtatish
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
        {!loading && tasks.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--brand-muted)]">
            Vazifalar yo&apos;q.{" "}
            <Link to="/logistics/transports" className="font-bold text-[var(--brand-primary)]">
              Mashina qo&apos;shing
            </Link>
          </p>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
