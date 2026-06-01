import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { BrandingProvider, useBranding } from "./context/BrandingContext";
import { LocaleProvider } from "./context/LocaleContext";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import ThemeApplicator from "./components/layout/ThemeApplicator";
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
import ChatPage from "./pages/ChatPage";
import TasksPage from "./pages/TasksPage";
import LlpPage from "./pages/LlpPage";
import LoadingSpinner from "./components/ui/LoadingSpinner";

function LoginRoute() {
  const { isLoggedIn, loading } = useAuth();
  if (loading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: "var(--brand-background)" }}
      >
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
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: "var(--brand-background)" }}
      >
        <LoadingSpinner />
      </div>
    );
  }
  return <Navigate to={isLoggedIn ? "/" : "/login"} replace />;
}

function AppRoutes() {
  const { branding } = useBranding();

  return (
    <LocaleProvider brandingDefaults={branding}>
      <ThemeApplicator>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<ProtectedRoute />}>
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="production" element={<ProductionPage />} />
            <Route path="warehouse" element={<WarehousePage />} />
            <Route path="shipping" element={<ShippingPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="llp" element={<LlpPage />} />
            <Route path="operators" element={<OperatorsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<CatchAllRoute />} />
        </Routes>
      </ThemeApplicator>
    </LocaleProvider>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <BrandingProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrandingProvider>
    </BrowserRouter>
  );
}
