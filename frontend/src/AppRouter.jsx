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
import InvoicesPage from "./pages/InvoicesPage";
import LoadingSpinner from "./components/ui/LoadingSpinner";

function LoginRoute() {
  const { isLoggedIn, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (isLoggedIn) return <Navigate to="/" replace />;
  return <LoginPage />;
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
            <Route path="operators" element={<OperatorsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="invoices" element={<InvoicesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
