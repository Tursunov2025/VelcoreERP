import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import FleetMap from "../../components/gps/FleetMap";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";

export default function LoadingPlansPage() {
  const [shipments, setShipments] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [form, setForm] = useState({ vehicle_id: "", driver_id: "", destination: "" });

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, v, d] = await Promise.all([
        api.logisticsShipments(),
        api.gpsVehicles(),
        api.gpsDrivers(),
      ]);
      setShipments(s.shipments || []);
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
      await api.logisticsCreateShipment({
        vehicle_id: form.vehicle_id ? Number(form.vehicle_id) : null,
        driver_id: form.driver_id ? Number(form.driver_id) : null,
        destination: form.destination,
        status: "planned",
      });
      setForm({ vehicle_id: "", driver_id: "", destination: "" });
      setToast("Reja yaratildi");
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const openDetail = async (id) => {
    try {
      const data = await api.logisticsShipment(id);
      setDetail(data);
    } catch (e) {
      setToast(e.message);
    }
  };

  const depart = async (id) => {
    try {
      await api.logisticsDepartShipment(id);
      setToast("Yo'lga chiqdi");
      load();
      if (detail?.id === id) openDetail(id);
    } catch (e) {
      setToast(e.message);
    }
  };

  const mapMarkers =
    detail?.gps_location?.latitude != null
      ? [
          {
            vehicle_id: detail.vehicle_id,
            plate_number: detail.vehicle?.plate_number,
            latitude: detail.gps_location.latitude,
            longitude: detail.gps_location.longitude,
            driver_name: detail.driver?.full_name,
          },
        ]
      : [];

  return (
    <div>
      <BackButton fallback="/logistics" label="Logistika" className="mb-4" />
      <PageHeader title="Yuklash Rejalari" subtitle="Shipment + mashina + haydovchi" />

      <form onSubmit={create} className="mb-6 grid gap-3 rounded-2xl border bg-[var(--brand-card)] p-4 sm:grid-cols-3">
        <select value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })} className="rounded-xl border px-3 py-2">
          <option value="">Mashina</option>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>{v.plate_number}</option>
          ))}
        </select>
        <select value={form.driver_id} onChange={(e) => setForm({ ...form, driver_id: e.target.value })} className="rounded-xl border px-3 py-2">
          <option value="">Haydovchi</option>
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>{d.full_name}</option>
          ))}
        </select>
        <input placeholder="Manzil" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} className="rounded-xl border px-3 py-2" />
        <button type="submit" className="brand-btn rounded-xl px-4 py-2 font-bold text-white sm:col-span-3" style={{ backgroundColor: "var(--brand-button)" }}>
          Reja yaratish
        </button>
      </form>

      <ErrorAlert message={error} onRetry={load} />
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-3">
          {shipments.map((s) => (
            <div key={s.id} className="rounded-2xl border bg-[var(--brand-card)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-bold">{s.shipment_no}</p>
                  <p className="text-sm text-[var(--brand-muted)]">
                    {s.destination || "—"} · {s.status}
                    {s.vehicle?.plate_number ? ` · ${s.vehicle.plate_number}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => openDetail(s.id)} className="rounded-xl border px-3 py-1 text-sm">
                    Batafsil
                  </button>
                  {s.status === "loading" || s.status === "planned" ? (
                    <button type="button" onClick={() => depart(s.id)} className="rounded-xl bg-green-600 px-3 py-1 text-sm text-white">
                      Yo'lga chiqish
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[var(--brand-card)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-bold">{detail.shipment_no}</h3>
              <button type="button" onClick={() => setDetail(null)} className="text-sm">Yopish</button>
            </div>
            <p className="mb-2 text-sm">Status: {detail.status} · {detail.destination}</p>
            {mapMarkers.length > 0 && (
              <FleetMap markers={mapMarkers} height="280px" className="mb-3 rounded-xl overflow-hidden" />
            )}
            <ul className="space-y-2 text-sm">
              {(detail.items || []).map((i) => (
                <li key={i.id} className="rounded border p-2">
                  {i.product?.product_name} × {i.qty} ({i.product?.product_code})
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
