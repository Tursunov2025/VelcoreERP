import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import OrderList from "../components/dashboard/OrderList";
import DashboardHeader from "../components/dashboard/DashboardHeader";
import OrderModal from "../components/modals/OrderModal";
import UserModal from "../components/modals/UserModal";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function OrdersPage() {
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

  const addOrder = async (data) => {
    const order = await api.createOrder(data);
    setOrders((prev) => [order, ...prev]);
  };

  const updateStatus = async (id, status) => {
    const updated = await api.updateOrderStatus(id, status);
    setOrders((prev) => prev.map((o) => (o.id === id ? updated : o)));
  };

  const deleteOrder = async (id) => {
    await api.deleteOrder(id);
    setOrders((prev) => prev.filter((o) => o.id !== id));
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader title="Zakazlar" subtitle="Barcha mijoz zakazlari" />
      <ErrorAlert message={error} onRetry={load} />
      <section className="rounded-[40px] bg-white p-5 shadow-xl md:p-8">
        <DashboardHeader
          search={search}
          onSearchChange={setSearch}
          isAdmin={isAdmin}
          onLogout={logout}
          onAddOrder={() => setShowOrderModal(true)}
          onAddUser={() => setShowUserModal(true)}
        />
        <OrderList
          orders={orders}
          search={search}
          isAdmin={isAdmin}
          onStatusChange={updateStatus}
          onDelete={deleteOrder}
        />
      </section>
      {showOrderModal && (
        <OrderModal onClose={() => setShowOrderModal(false)} onSave={addOrder} />
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
