import { useState } from "react";
import LoginPage from "./components/auth/LoginPage";
import DashboardHeader from "./components/dashboard/DashboardHeader";
import OrderList from "./components/dashboard/OrderList";
import StatsCards from "./components/dashboard/StatsCards";
import DashboardLayout from "./components/layout/DashboardLayout";
import OrderModal from "./components/modals/OrderModal";
import UserModal from "./components/modals/UserModal";
import { useAuth } from "./hooks/useAuth";
import { useOrders } from "./hooks/useOrders";
import { useUsers } from "./hooks/useUsers";

export default function App() {
  const {
    username,
    role,
    isAdmin,
    isLoggedIn,
    loginError,
    isSubmitting,
    login,
    logout,
  } = useAuth();

  const { users, loading: usersLoading, error: usersError, fetchUsers, createUser } =
    useUsers({ enabled: !isLoggedIn });

  const {
    orders,
    loading: ordersLoading,
    error: ordersError,
    addOrder,
    updateOrderStatus,
    deleteOrder,
  } = useOrders({ enabled: isLoggedIn });

  const [search, setSearch] = useState("");
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);

  if (!isLoggedIn) {
    return (
      <LoginPage
        users={users}
        loading={usersLoading}
        usersError={usersError}
        loginError={loginError}
        isSubmitting={isSubmitting}
        onLogin={login}
        onRefreshUsers={fetchUsers}
      />
    );
  }

  return (
    <DashboardLayout username={username} role={role}>
      <StatsCards orders={orders} />

      <section className="rounded-[40px] bg-white p-5 shadow-xl md:p-8">
        <DashboardHeader
          search={search}
          onSearchChange={setSearch}
          isAdmin={isAdmin}
          onLogout={logout}
          onAddOrder={() => setShowOrderModal(true)}
          onAddUser={() => setShowUserModal(true)}
        />

        {ordersLoading && (
          <p className="mb-4 text-center text-gray-500">Zakazlar yuklanmoqda...</p>
        )}

        {ordersError && (
          <p className="mb-4 text-center text-sm text-red-500">{ordersError}</p>
        )}

        <OrderList
          orders={orders}
          search={search}
          isAdmin={isAdmin}
          onStatusChange={updateOrderStatus}
          onDelete={deleteOrder}
        />
      </section>

      {showOrderModal && (
        <OrderModal
          onClose={() => setShowOrderModal(false)}
          onSave={addOrder}
        />
      )}

      {showUserModal && isAdmin && (
        <UserModal
          onClose={() => setShowUserModal(false)}
          onSave={createUser}
        />
      )}
    </DashboardLayout>
  );
}
