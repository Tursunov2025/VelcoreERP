import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import FleetMap from "../../components/gps/FleetMap";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";

export default function InTransitPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const data = await api.logisticsShipments("in_transit");
    setShipments(data.shipments || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markers = shipments
    .filter((s) => s.gps_location?.latitude != null)
    .map((s) => ({
      vehicle_id: s.vehicle_id,
      plate_number: s.vehicle?.plate_number,
      latitude: s.gps_location.latitude,
      longitude: s.gps_location.longitude,
      driver_name: s.driver?.full_name,
    }));

  return (
    <div>
      <BackButton fallback="/logistics" label="Logistika" className="mb-4" />
      <PageHeader title="Yo'ldagi Yuklar" subtitle="in_transit shipmentlar + GPS" />
      {markers.length > 0 && <FleetMap markers={markers} height="360px" className="mb-4 rounded-2xl overflow-hidden" />}
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-3">
          {shipments.map((s) => (
            <div key={s.id} className="rounded-2xl border bg-[var(--brand-card)] p-4">
              <p className="font-bold">{s.shipment_no}</p>
              <p className="text-sm text-[var(--brand-muted)]">
                {s.destination} · {s.vehicle?.plate_number || "—"} · {s.driver?.full_name || "—"}
              </p>
            </div>
          ))}
          {shipments.length === 0 && <p className="text-center text-[var(--brand-muted)]">Yo'ldagi yuk yo'q</p>}
        </div>
      )}
    </div>
  );
}
