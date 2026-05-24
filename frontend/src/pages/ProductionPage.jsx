import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ORDER_STATUSES } from "../constants/orderStatuses";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function ProductionPage() {
  const [active, setActive] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [activeData, stats] = await Promise.all([
        api.getActiveProduction(),
        api.getProductionAnalytics(),
      ]);
      setActive(activeData);
      setAnalytics(stats);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTimeline = async (orderId) => {
    setSelectedId(orderId);
    const data = await api.getProductionTimeline(orderId);
    setTimeline(data);
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Ishlab chiqarish"
        subtitle="Bosqichlar va real vaqt holati"
      />
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <p className="text-sm text-gray-500">Jami</p>
          <p className="text-2xl font-black">{analytics?.total_orders ?? 0}</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Ishlab chiqarishda</p>
          <p className="text-2xl font-black">{analytics?.in_production ?? 0}</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Tayyor</p>
          <p className="text-2xl font-black text-green-600">
            {analytics?.completed ?? 0}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Bosqichlar</p>
          <p className="text-2xl font-black">{ORDER_STATUSES.length}</p>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-bold">Faol zakazlar</h2>
          <div className="max-h-96 space-y-3 overflow-y-auto">
            {active.map((order) => (
              <button
                key={order.id}
                type="button"
                onClick={() => loadTimeline(order.id)}
                className={`w-full rounded-2xl border p-4 text-left transition hover:shadow ${
                  selectedId === order.id ? "border-black bg-gray-50" : ""
                }`}
              >
                <p className="font-bold">#{order.id} — {order.client}</p>
                <p className="text-sm text-gray-500">{order.status}</p>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 font-bold">
            Timeline {selectedId ? `#${selectedId}` : ""}
          </h2>
          {!selectedId ? (
            <p className="text-gray-500">Zakaz tanlang</p>
          ) : (
            <div className="space-y-3">
              {timeline.map((log) => (
                <div key={log.id} className="border-l-4 border-black pl-4">
                  <p className="font-bold">{log.stage}</p>
                  <p className="text-sm text-gray-500">
                    {log.changed_by} —{" "}
                    {log.created_at
                      ? new Date(log.created_at).toLocaleString()
                      : ""}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
