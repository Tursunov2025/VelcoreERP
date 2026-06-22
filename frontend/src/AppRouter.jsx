import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { isTraceabilityEnabledForRoutes } from "./constants/featureFlags";
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
import OrdersControlCenterPage from "./pages/OrdersControlCenterPage";
import ChatPage from "./pages/ChatPage";
import TasksPage from "./pages/TasksPage";
import LlpPage from "./pages/LlpPage";
import ExportShipmentsPage from "./pages/ExportShipmentsPage";
import CrmPage from "./pages/CrmPage";
import CurrenciesPage from "./pages/CurrenciesPage";
import TransportPage from "./pages/TransportPage";
import LiveMapPage from "./pages/LiveMapPage";
import DriverTrackingPage from "./pages/DriverTrackingPage";
import VehiclesPage from "./pages/VehiclesPage";
import DriversPage from "./pages/DriversPage";
import GpsMonitoringHubPage from "./pages/gps/GpsMonitoringHubPage";
import TransportTasksPage from "./pages/gps/TransportTasksPage";
import DriverMobilePage from "./pages/driver/DriverMobilePage";
import WarehouseForecastPage from "./pages/WarehouseForecastPage";
import MesHubPage from "./pages/mes/MesHubPage";
import MesCategoriesPage from "./pages/mes/MesCategoriesPage";
import MesPartsPage from "./pages/mes/MesPartsPage";
import MesTemplatesPage from "./pages/mes/MesTemplatesPage";
import MesTemplateFormPage from "./pages/mes/MesTemplateFormPage";
import MesTemplateDetailPage from "./pages/mes/MesTemplateDetailPage";
import MesJobsPage from "./pages/mes/MesJobsPage";
import MesJobFormPage from "./pages/mes/MesJobFormPage";
import MesJobDetailPage from "./pages/mes/MesJobDetailPage";
import LazerTerminalQueuePage from "./pages/mes/LazerTerminalQueuePage";
import LazerTerminalJobPage from "./pages/mes/LazerTerminalJobPage";
import SvarshikTerminalQueuePage from "./pages/mes/SvarshikTerminalQueuePage";
import SvarshikTerminalJobPage from "./pages/mes/SvarshikTerminalJobPage";
import MesProductionMonitorPage from "./pages/mes/MesProductionMonitorPage";
import KraskaTerminalQueuePage from "./pages/mes/KraskaTerminalQueuePage";
import KraskaTerminalJobPage from "./pages/mes/KraskaTerminalJobPage";
import QcTerminalQueuePage from "./pages/mes/QcTerminalQueuePage";
import QcTerminalJobPage from "./pages/mes/QcTerminalJobPage";
import MesQcRejectionReasonsPage from "./pages/mes/MesQcRejectionReasonsPage";
import PackagingTerminalQueuePage from "./pages/mes/PackagingTerminalQueuePage";
import PackagingTerminalJobPage from "./pages/mes/PackagingTerminalJobPage";
import WarehouseTerminalQueuePage from "./pages/mes/WarehouseTerminalQueuePage";
import WarehouseTerminalJobPage from "./pages/mes/WarehouseTerminalJobPage";
import MesWarehouseLocationsPage from "./pages/mes/MesWarehouseLocationsPage";
import DispatchTerminalQueuePage from "./pages/mes/DispatchTerminalQueuePage";
import DispatchTerminalJobPage from "./pages/mes/DispatchTerminalJobPage";
import MaterialsHubPage from "./pages/materials/MaterialsHubPage";
import MaterialsCategoriesPage from "./pages/materials/MaterialsCategoriesPage";
import MaterialsItemsPage from "./pages/materials/MaterialsItemsPage";
import MaterialsReceiptsPage from "./pages/materials/MaterialsReceiptsPage";
import MaterialsIssuesPage from "./pages/materials/MaterialsIssuesPage";
import MaterialsAdjustmentsPage from "./pages/materials/MaterialsAdjustmentsPage";
import MaterialsMovementsPage from "./pages/materials/MaterialsMovementsPage";
import MaterialPartBomPage from "./pages/materials/MaterialPartBomPage";
import MaterialsShortagesPage from "./pages/materials/MaterialsShortagesPage";
import MaterialsConsumptionRulesPage from "./pages/materials/MaterialsConsumptionRulesPage";
import MaterialsConsumptionsPage from "./pages/materials/MaterialsConsumptionsPage";
import LoadingSpinner from "./components/ui/LoadingSpinner";
import MobileUpdateGate from "./components/mobile/MobileUpdateGate";
import PackagePassportPage from "./pages/traceability/PackagePassportPage";
import PublicPackageTrackPage from "./pages/traceability/PublicPackageTrackPage";
import PackageScannerPage from "./pages/traceability/PackageScannerPage";

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
  const traceabilityEnabled = isTraceabilityEnabledForRoutes();

  return (
    <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/driver" element={<DriverMobilePage />} />
          {traceabilityEnabled ? (
            <Route path="/track/package/:labelCode" element={<PublicPackageTrackPage />} />
          ) : null}
          <Route element={<ProtectedRoute />}>
            {traceabilityEnabled ? (
              <>
                <Route path="packages/:labelCode" element={<PackagePassportPage />} />
                <Route path="scanner" element={<PackageScannerPage />} />
              </>
            ) : null}
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="production" element={<ProductionPage />} />
            <Route path="warehouse" element={<WarehousePage />} />
            <Route path="shipping" element={<ShippingPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="llp" element={<LlpPage />} />
            <Route path="export-shipments" element={<ExportShipmentsPage />} />
            <Route path="crm" element={<CrmPage />} />
            <Route path="currencies" element={<CurrenciesPage />} />
            <Route path="transport" element={<TransportPage />} />
            <Route path="transport/live-map" element={<LiveMapPage />} />
            <Route path="transport/vehicles" element={<VehiclesPage />} />
            <Route path="transport/drivers" element={<DriversPage />} />
            <Route path="driver-tracking" element={<DriverTrackingPage />} />
            <Route path="gps" element={<GpsMonitoringHubPage />} />
            <Route path="gps/monitoring" element={<LiveMapPage />} />
            <Route path="gps/transports" element={<TransportPage />} />
            <Route path="gps/vehicles" element={<VehiclesPage />} />
            <Route path="gps/drivers" element={<DriversPage />} />
            <Route path="gps/tasks" element={<TransportTasksPage />} />
            <Route path="materials/forecast" element={<WarehouseForecastPage />} />
            <Route path="mes" element={<MesHubPage />} />
            <Route path="mes/categories" element={<MesCategoriesPage />} />
            <Route path="mes/parts" element={<MesPartsPage />} />
            <Route path="mes/templates" element={<MesTemplatesPage />} />
            <Route path="mes/templates/new" element={<MesTemplateFormPage />} />
            <Route path="mes/templates/:id/edit" element={<MesTemplateFormPage />} />
            <Route path="mes/templates/:id" element={<MesTemplateDetailPage />} />
            <Route path="mes/jobs" element={<MesJobsPage />} />
            <Route path="mes/jobs/new" element={<MesJobFormPage />} />
            <Route path="mes/jobs/:id/edit" element={<MesJobFormPage />} />
            <Route path="mes/jobs/:id" element={<MesJobDetailPage />} />
            <Route path="mes/monitor" element={<MesProductionMonitorPage />} />
            <Route path="mes/terminal/lazer" element={<LazerTerminalQueuePage />} />
            <Route path="mes/terminal/lazer/jobs/:id" element={<LazerTerminalJobPage />} />
            <Route path="mes/terminal/svarshik" element={<SvarshikTerminalQueuePage />} />
            <Route path="mes/terminal/svarshik/jobs/:id" element={<SvarshikTerminalJobPage />} />
            <Route path="mes/terminal/kraska" element={<KraskaTerminalQueuePage />} />
            <Route path="mes/terminal/kraska/jobs/:id" element={<KraskaTerminalJobPage />} />
            <Route path="mes/terminal/qc" element={<QcTerminalQueuePage />} />
            <Route path="mes/terminal/qc/jobs/:id" element={<QcTerminalJobPage />} />
            <Route path="mes/qc/rejection-reasons" element={<MesQcRejectionReasonsPage />} />
            <Route path="mes/terminal/packaging" element={<PackagingTerminalQueuePage />} />
            <Route path="mes/terminal/packaging/jobs/:id" element={<PackagingTerminalJobPage />} />
            <Route path="mes/terminal/warehouse" element={<WarehouseTerminalQueuePage />} />
            <Route path="mes/terminal/warehouse/jobs/:id" element={<WarehouseTerminalJobPage />} />
            <Route path="mes/warehouse/locations" element={<MesWarehouseLocationsPage />} />
            <Route path="mes/terminal/dispatch" element={<DispatchTerminalQueuePage />} />
            <Route path="mes/terminal/dispatch/jobs/:id" element={<DispatchTerminalJobPage />} />
            <Route path="materials" element={<MaterialsHubPage />} />
            <Route path="materials/categories" element={<MaterialsCategoriesPage />} />
            <Route path="materials/items" element={<MaterialsItemsPage />} />
            <Route path="materials/receipts" element={<MaterialsReceiptsPage />} />
            <Route path="materials/issues" element={<MaterialsIssuesPage />} />
            <Route path="materials/adjustments" element={<MaterialsAdjustmentsPage />} />
            <Route path="materials/movements" element={<MaterialsMovementsPage />} />
            <Route path="materials/shortages" element={<MaterialsShortagesPage />} />
            <Route path="materials/part-bom" element={<MaterialPartBomPage />} />
            <Route path="materials/consumption-rules" element={<MaterialsConsumptionRulesPage />} />
            <Route path="materials/consumed-today" element={<MaterialsConsumptionsPage />} />
            <Route path="operators" element={<OperatorsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="control-center" element={<OrdersControlCenterPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<CatchAllRoute />} />
    </Routes>
  );
}

function AppProviders() {
  const { branding } = useBranding();

  return (
    <AuthProvider>
      <LocaleProvider brandingDefaults={branding}>
        <MobileUpdateGate>
          <ThemeApplicator>
            <AppRoutes />
          </ThemeApplicator>
        </MobileUpdateGate>
      </LocaleProvider>
    </AuthProvider>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <BrandingProvider>
        <AppProviders />
      </BrandingProvider>
    </BrowserRouter>
  );
}
