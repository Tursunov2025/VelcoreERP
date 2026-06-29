import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";

export default function LoadingControlPage() {
  const [shipments, setShipments] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [scan, setScan] = useState({ barcode: "", shipment_id: "", vehicle_id: "", driver_id: "", qty: 1 });

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, v, d] = await Promise.all([
        api.logisticsShipments("planned"),
        api.gpsVehicles(),
        api.gpsDrivers(),
      ]);
      const loadingList = await api.logisticsShipments("loading");
      setShipments([...(s.shipments || []), ...(loadingList.shipments || [])]);
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

  const submitScan = async (e) => {
    e.preventDefault();
    if (!scan.barcode || !scan.shipment_id) {
      setToast("Barcode va shipment tanlang");
      return;
    }
    try {
      const res = await api.logisticsLoadingScan({
        barcode: scan.barcode.trim(),
        shipment_id: Number(scan.shipment_id),
        vehicle_id: scan.vehicle_id ? Number(scan.vehicle_id) : null,
        driver_id: scan.driver_id ? Number(scan.driver_id) : null,
        qty: Number(scan.qty) || 1,
      });
      setToast(`Yuklandi: ${res.product?.product_name}`);
      setScan((s) => ({ ...s, barcode: "" }));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <BackButton fallback="/logistics" label="Logistika" className="mb-4" />
      <PageHeader title="Yuklash Nazorati" subtitle="Barcode/QR — Mahsulot → Mashina → Haydovchi" />

      {loading ? (
        <LoadingSpinner />
      ) : (
        <form onSubmit={submitScan} className="grid max-w-xl gap-3 rounded-2xl border bg-[var(--brand-card)] p-4">
          <input
            autoFocus
            placeholder="Barcode / QR skaner"
            value={scan.barcode}
            onChange={(e) => setScan({ ...scan, barcode: e.target.value })}
            className="rounded-xl border px-4 py-3 text-lg font-mono"
          />
          <select
            value={scan.shipment_id}
            onChange={(e) => setScan({ ...scan, shipment_id: e.target.value })}
            className="rounded-xl border px-3 py-2"
            required
          >
            <option value="">Shipment tanlang</option>
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.shipment_no} — {s.destination}
              </option>
            ))}
          </select>
          <select value={scan.vehicle_id} onChange={(e) => setScan({ ...scan, vehicle_id: e.target.value })} className="rounded-xl border px-3 py-2">
            <option value="">Mashina</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>{v.plate_number}</option>
            ))}
          </select>
          <select value={scan.driver_id} onChange={(e) => setScan({ ...scan, driver_id: e.target.value })} className="rounded-xl border px-3 py-2">
            <option value="">Haydovchi</option>
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>{d.full_name}</option>
            ))}
          </select>
          <input type="number" min="0.01" step="0.01" value={scan.qty} onChange={(e) => setScan({ ...scan, qty: e.target.value })} className="rounded-xl border px-3 py-2" />
          <button type="submit" className="brand-btn rounded-xl py-3 font-bold text-white" style={{ backgroundColor: "var(--brand-button)" }}>
            Skaner qilish
          </button>
        </form>
      )}
      <ErrorAlert message={error} onRetry={load} />
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
