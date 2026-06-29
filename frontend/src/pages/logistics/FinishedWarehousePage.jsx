import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";

const STATUSES = ["Available", "Reserved", "Loaded", "Delivered"];

const STATUS_LABELS = {
  Available: "Available",
  Reserved: "Reserved",
  Loaded: "Loaded",
  Delivered: "Delivered",
};

export default function FinishedWarehousePage() {
  const [products, setProducts] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [form, setForm] = useState({
    product_code: "",
    product_name: "",
    order_number: "",
    quantity: 1,
    warehouse_location: "",
    status: "Available",
    vehicle_id: "",
    driver_id: "",
  });

  const load = useCallback(async () => {
    setError("");
    try {
      const [data, v, d] = await Promise.all([
        api.logisticsProducts(),
        api.gpsVehicles().catch(() => ({ vehicles: [] })),
        api.gpsDrivers().catch(() => ({ drivers: [] })),
      ]);
      setProducts(data.products || []);
      setVehicles(v.vehicles || []);
      setDrivers(d.drivers || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.logisticsCreateProduct({
        ...form,
        vehicle_id: form.vehicle_id ? Number(form.vehicle_id) : null,
        driver_id: form.driver_id ? Number(form.driver_id) : null,
      });
      setForm({
        product_code: "",
        product_name: "",
        order_number: "",
        quantity: 1,
        warehouse_location: "",
        status: "Available",
        vehicle_id: "",
        driver_id: "",
      });
      setToast("Mahsulot qo'shildi");
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <BackButton fallback="/logistics" label="Logistika" className="mb-4" />
      <PageHeader title="Tayyor Mahsulot Ombori" subtitle="Tayyor mahsulotlar ro'yxati" />

      <form onSubmit={create} className="mb-6 grid gap-3 rounded-2xl border bg-[var(--brand-card)] p-4 sm:grid-cols-2">
        <input
          placeholder="Mahsulot kodi *"
          value={form.product_code}
          onChange={(e) => setForm({ ...form, product_code: e.target.value })}
          className="rounded-xl border px-3 py-2"
          required
        />
        <input
          placeholder="Mahsulot nomi *"
          value={form.product_name}
          onChange={(e) => setForm({ ...form, product_name: e.target.value })}
          className="rounded-xl border px-3 py-2"
          required
        />
        <input
          placeholder="Buyurtma raqami"
          value={form.order_number}
          onChange={(e) => setForm({ ...form, order_number: e.target.value })}
          className="rounded-xl border px-3 py-2"
        />
        <input
          type="number"
          min="0.01"
          step="0.01"
          placeholder="Soni"
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
          className="rounded-xl border px-3 py-2"
        />
        <input
          placeholder="Ombor joylashuvi"
          value={form.warehouse_location}
          onChange={(e) => setForm({ ...form, warehouse_location: e.target.value })}
          className="rounded-xl border px-3 py-2"
        />
        <select
          value={form.vehicle_id}
          onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}
          className="rounded-xl border px-3 py-2"
        >
          <option value="">Mashina (ixtiyoriy)</option>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.plate_number || v.model || `#${v.id}`}
            </option>
          ))}
        </select>
        <select
          value={form.driver_id}
          onChange={(e) => setForm({ ...form, driver_id: e.target.value })}
          className="rounded-xl border px-3 py-2"
        >
          <option value="">Haydovchi (ixtiyoriy)</option>
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>
              {d.full_name || d.phone || `#${d.id}`}
            </option>
          ))}
        </select>
        <select
          value={form.status}
          onChange={(e) => setForm({ ...form, status: e.target.value })}
          className="rounded-xl border px-3 py-2"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <button type="submit" className="brand-btn rounded-xl px-4 py-2 font-bold text-white sm:col-span-2" style={{ backgroundColor: "var(--brand-button)" }}>
          Qo'shish
        </button>
      </form>

      <ErrorAlert message={error} onRetry={load} />
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="overflow-x-auto rounded-2xl border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="p-3">Kod</th>
                <th className="p-3">Nomi</th>
                <th className="p-3">Buyurtma</th>
                <th className="p-3">Soni</th>
                <th className="p-3">Mashina</th>
                <th className="p-3">Haydovchi</th>
                <th className="p-3">Joy</th>
                <th className="p-3">Status</th>
                <th className="p-3">Barcode</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="p-3 font-mono">{p.product_code}</td>
                  <td className="p-3">{p.product_name}</td>
                  <td className="p-3">{p.order_number || "—"}</td>
                  <td className="p-3">{p.quantity}</td>
                  <td className="p-3">{p.vehicle?.plate_number || "—"}</td>
                  <td className="p-3">{p.driver?.full_name || "—"}</td>
                  <td className="p-3">{p.warehouse_location || "—"}</td>
                  <td className="p-3">{p.status}</td>
                  <td className="p-3 font-mono text-xs">{p.barcode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
