import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import WorkflowOrderCard from "../components/workflow/WorkflowOrderCard";
import OrderModal from "../components/modals/OrderModal";
import UserModal from "../components/modals/UserModal";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useLocale } from "../context/LocaleContext";

export default function OrdersPage() {
  const { t } = useLocale();
  const { isAdmin, logout } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setOrders(await api.getOrders());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = orders.filter((o) => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (
      o.client?.toLowerCase().includes(q) ||
      o.destination?.toLowerCase().includes(q) ||
      String(o.id).includes(q)
    );
  });

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title={t("orders.title")}
        subtitle={t("orders.subtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowOrderModal(true)}
              className="rounded-2xl bg-black px-5 py-2 text-sm text-white"
            >
              + Yangi zakaz
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={() => setShowUserModal(true)}
                className="rounded-2xl bg-blue-600 px-5 py-2 text-sm text-white"
              >
                + User
              </button>
            )}
            <button
              type="button"
              onClick={logout}
              className="rounded-2xl bg-red-500 px-5 py-2 text-sm text-white"
            >
              Chiqish
            </button>
          </div>
        }
      />

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Qidirish..."
        className="mb-6 w-full rounded-2xl border px-5 py-4 md:max-w-md"
      />

      <ErrorAlert message={error} onRetry={load} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((order) => (
          <WorkflowOrderCard
            key={order.id}
            order={order}
            onComplete={(id, body) => api.completeOrder(id, body).then(load)}
            onVerify={(id, body) => api.verifyOrder(id, body).then(load)}
            onRefresh={load}
          />
        ))}
      </div>

      {showOrderModal && (
        <OrderModal
          onClose={() => setShowOrderModal(false)}
          onSave={async (data) => {
            await api.createOrder(data);
            load();
          }}
        />
      )}
      {showUserModal && isAdmin && (
        <UserModal
          onClose={() => setShowUserModal(false)}
          onSave={async (data) => {
            await api.createUser(data);
            setShowUserModal(false);
          }}
        />
      )}
    </div>
  );
}
