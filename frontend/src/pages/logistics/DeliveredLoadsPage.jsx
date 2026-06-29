import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";

export default function DeliveredLoadsPage() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    const data = await api.logisticsShipments("delivered");
    setShipments(data.shipments || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markDelivered = async (id) => {
    try {
      await api.logisticsDeliverShipment(id);
      setToast("Yetkazildi deb belgilandi");
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <BackButton fallback="/logistics" label="Logistika" className="mb-4" />
      <PageHeader title="Yetkazib Berilgan Yuklar" subtitle="delivered status" />
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-3">
          {shipments.map((s) => (
            <div key={s.id} className="rounded-2xl border bg-[var(--brand-card)] p-4">
              <p className="font-bold">{s.shipment_no}</p>
              <p className="text-sm text-[var(--brand-muted)]">
                {s.destination} · {s.delivered_at ? new Date(s.delivered_at).toLocaleString() : "—"}
              </p>
            </div>
          ))}
          {shipments.length === 0 && <p className="text-center text-[var(--brand-muted)]">Hali yetkazilgan yuk yo'q</p>}
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
