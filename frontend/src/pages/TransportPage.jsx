import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const STATUSES = ["Draft", "Loaded", "In Transit", "Border", "Delivered"];

const STATUS_STYLE = {
  Draft: "bg-gray-100 text-gray-700",
  Loaded: "bg-blue-100 text-blue-700",
  "In Transit": "bg-amber-100 text-amber-700",
  Border: "bg-purple-100 text-purple-700",
  Delivered: "bg-green-100 text-green-700",
};

const STATUS_EMOJI = {
  Draft: "📝",
  Loaded: "📦",
  "In Transit": "🚚",
  Border: "🛃",
  Delivered: "✅",
};

const emptyForm = {
  vehicle: "",
  driver_name: "",
  driver_phone: "",
  shipment_weight_kg: "",
  export_shipment_id: "",
  notes: "",
};

function nextStatuses(current) {
  const idx = STATUSES.indexOf(current);
  return idx >= 0 && idx < STATUSES.length - 1 ? [STATUSES[idx + 1]] : [];
}

export default function TransportPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("export_manage");

  const [transports, setTransports] = useState([]);
  const [shipments, setShipments] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm });

  const load = async () => {
    setError("");
    try {
      const [list, shipmentList] = await Promise.all([
        api.transports({ status: statusFilter, q: search }),
        api.exportShipments().catch(() => ({ shipments: [] })),
      ]);
      setTransports(list.transports || []);
      setShipments(shipmentList.shipments || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = window.setTimeout(load, 250);
    return () => window.clearTimeout(id);
  }, [statusFilter, search]);

  const counts = useMemo(() => {
    const result = { total: transports.length };
    STATUSES.forEach((s) => {
      result[s] = transports.filter((t) => t.status === s).length;
    });
    return result;
  }, [transports]);

  const createTransport = async (e) => {
    e.preventDefault();
    if (!form.vehicle.trim()) return;
    try {
      await api.createTransport({
        vehicle: form.vehicle,
        driver_name: form.driver_name,
        driver_phone: form.driver_phone,
        shipment_weight_kg: Number(form.shipment_weight_kg) || 0,
        export_shipment_id: form.export_shipment_id ? Number(form.export_shipment_id) : null,
        notes: form.notes,
      });
      setToast("Transport created");
      setForm({ ...emptyForm });
      setShowForm(false);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const setStatus = async (transport, status) => {
    try {
      await api.updateTransportStatus(transport.id, status);
      setToast(`${transport.vehicle} → ${status}`);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div className="pb-24">
      <BackButton fallback="/export-shipments" label="Export & Logistics" className="mb-4" />
      <PageHeader title="Transport Management" subtitle="Vehicles, drivers and delivery tracking" />

      <div className="mb-4 flex flex-wrap gap-2">
        <Link
          to="/transport/live-map"
          className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          📍 Live Map
        </Link>
        <Link
          to="/driver-tracking"
          className="rounded-xl border px-4 py-2.5 text-sm font-bold text-[var(--brand-text)]"
        >
          Driver GPS
        </Link>
      </div>

      {/* Status summary */}
      <div className="mb-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-3 text-center">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Total</p>
          <p className="text-xl font-black">{counts.total}</p>
        </div>
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(statusFilter === s ? "" : s)}
            className={`rounded-2xl border bg-[var(--brand-card)] p-3 text-center ${
              statusFilter === s ? "ring-2 ring-[var(--brand-button)]" : ""
            }`}
          >
            <p className="text-xs uppercase text-[var(--brand-muted)]">
              {STATUS_EMOJI[s]} {s}
            </p>
            <p className="text-xl font-black">{counts[s]}</p>
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search vehicle / driver / phone..."
          className="flex-1 rounded-xl border bg-[var(--brand-card)] px-4 py-3 text-[var(--brand-text)]"
        />
        {canManage ? (
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl px-4 py-3 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            + New Transport
          </button>
        ) : null}
      </div>

      {showForm && canManage ? (
        <form
          onSubmit={createTransport}
          className="mb-6 grid gap-2 rounded-3xl border bg-[var(--brand-card)] p-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <input
            value={form.vehicle}
            onChange={(e) => setForm({ ...form, vehicle: e.target.value })}
            placeholder="Vehicle (e.g. KamAZ 01 A 777 AA)"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <input
            value={form.driver_name}
            onChange={(e) => setForm({ ...form, driver_name: e.target.value })}
            placeholder="Driver name"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <input
            value={form.driver_phone}
            onChange={(e) => setForm({ ...form, driver_phone: e.target.value })}
            placeholder="Driver phone"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <input
            type="number"
            min="0"
            step="any"
            value={form.shipment_weight_kg}
            onChange={(e) => setForm({ ...form, shipment_weight_kg: e.target.value })}
            placeholder="Shipment weight (kg)"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <select
            value={form.export_shipment_id}
            onChange={(e) => setForm({ ...form, export_shipment_id: e.target.value })}
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          >
            <option value="">No export shipment</option>
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.shipment_number} — {s.customer}
              </option>
            ))}
          </select>
          <input
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Notes"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-bold text-white sm:col-span-2 lg:col-span-1"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Create
          </button>
        </form>
      ) : null}

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-3">
        {transports.map((transport) => (
          <div key={transport.id} className="rounded-3xl border bg-[var(--brand-card)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-lg font-black text-[var(--brand-text)]">
                  🚛 {transport.vehicle}
                </p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {transport.driver_name || "—"}
                  {transport.driver_phone ? ` · ${transport.driver_phone}` : ""}
                </p>
                {transport.export_shipment_number ? (
                  <p className="text-xs font-semibold text-blue-600">
                    {transport.export_shipment_number} · {transport.export_customer}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-3 py-1 text-sm font-bold ${
                    STATUS_STYLE[transport.status] || STATUS_STYLE.Draft
                  }`}
                >
                  {STATUS_EMOJI[transport.status]} {transport.status}
                </span>
                {canManage &&
                  nextStatuses(transport.status).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStatus(transport, s)}
                      className="rounded-xl px-3 py-1.5 text-xs font-bold text-white"
                      style={{ backgroundColor: "var(--brand-button)" }}
                    >
                      → {s}
                    </button>
                  ))}
              </div>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <p className="text-xs text-[var(--brand-muted)]">Weight</p>
                <p className="font-bold">{transport.shipment_weight_kg || 0} kg</p>
              </div>
              <div>
                <p className="text-xs text-[var(--brand-muted)]">Departure</p>
                <p className="font-bold">
                  {transport.departure_date
                    ? new Date(transport.departure_date).toLocaleDateString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--brand-muted)]">Arrival</p>
                <p className="font-bold">
                  {transport.arrival_date
                    ? new Date(transport.arrival_date).toLocaleDateString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--brand-muted)]">Created by</p>
                <p className="font-bold">{transport.created_by}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setExpanded(expanded === transport.id ? null : transport.id)}
              className="mt-3 text-sm font-semibold text-[var(--brand-primary)]"
            >
              {expanded === transport.id ? "▾ Hide timeline" : "▸ Shipment timeline"}
            </button>

            {expanded === transport.id ? (
              <div className="mt-3 border-l-2 border-[var(--brand-button)] pl-4">
                {(transport.events || []).map((event) => (
                  <div key={event.id} className="relative mb-3">
                    <span className="absolute -left-[1.45rem] top-1 h-3 w-3 rounded-full bg-[var(--brand-button)]" />
                    <p className="text-sm font-bold text-[var(--brand-text)]">
                      {STATUS_EMOJI[event.status]} {event.status}
                    </p>
                    <p className="text-xs text-[var(--brand-muted)]">
                      {event.created_at ? new Date(event.created_at).toLocaleString() : "—"} ·{" "}
                      {event.created_by}
                      {event.comment ? ` — ${event.comment}` : ""}
                    </p>
                  </div>
                ))}
                {transport.gps?.latest ? (
                  <div className="mt-3 rounded-xl border bg-[var(--brand-background)] p-3 text-sm">
                    <p className="font-bold text-[var(--brand-text)]">📍 Live GPS</p>
                    <p className="text-[var(--brand-muted)]">
                      {transport.gps.vehicle?.plate_number} · {transport.gps.driver?.full_name}
                    </p>
                    <p>
                      {transport.gps.latest.latitude?.toFixed(5)},{" "}
                      {transport.gps.latest.longitude?.toFixed(5)} · {transport.gps.latest.speed}{" "}
                      km/h
                    </p>
                    <p className="text-xs text-[var(--brand-muted)]">
                      Updated:{" "}
                      {transport.gps.latest.recorded_at
                        ? new Date(transport.gps.latest.recorded_at).toLocaleString()
                        : "—"}
                      {transport.gps.latest.online ? " · Online" : " · Offline"}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
        {!loading && transports.length === 0 ? (
          <p className="py-12 text-center text-sm text-[var(--brand-muted)]">No transports yet</p>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
