import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import OrdersPage from "./pages/OrdersPage";
import ProductionPage from "./pages/ProductionPage";
import WarehousePage from "./pages/WarehousePage";
import OperatorsPage from "./pages/OperatorsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import FinancePage from "./pages/FinancePage";
import ShippingPage from "./pages/ShippingPage";
import InvoicesPage from "./pages/InvoicesPage";
import SettingsPage from "./pages/SettingsPage";
import LoadingSpinner from "./components/ui/LoadingSpinner";

function LoginRoute() {
  const { isLoggedIn, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f5f6fa]">
        <LoadingSpinner />
      </div>
    );
  }
  if (isLoggedIn) return <Navigate to="/" replace />;
  return <LoginPage />;
}

function CatchAllRoute() {
  const { isLoggedIn, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f5f6fa]">
        <LoadingSpinner />
      </div>
    );
  }
  return <Navigate to={isLoggedIn ? "/" : "/login"} replace />;
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<ProtectedRoute />}>
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="production" element={<ProductionPage />} />
            <Route path="warehouse" element={<WarehousePage />} />
            <Route path="shipping" element={<ShippingPage />} />
            <Route path="operators" element={<OperatorsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<CatchAllRoute />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
