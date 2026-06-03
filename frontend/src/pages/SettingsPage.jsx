import { useState } from "react";
import AdminRoute from "../components/layout/AdminRoute";
import PageHeader from "../components/ui/PageHeader";
import SettingsLayout from "../components/settings/SettingsLayout";
import { useLocale } from "../context/LocaleContext";
import UsersTab from "../components/settings/UsersTab";
import AppearanceTab from "../components/settings/AppearanceTab";
import PermissionsTab from "../components/settings/PermissionsTab";
import TelegramTab from "../components/settings/TelegramTab";
import NotificationsTab from "../components/settings/NotificationsTab";
import OrdersTab from "../components/settings/OrdersTab";
import SearchTab from "../components/settings/SearchTab";
import OnlineTab from "../components/settings/OnlineTab";
import AuditTab from "../components/settings/AuditTab";
import BackupTab from "../components/settings/BackupTab";
import MigrationTab from "../components/settings/MigrationTab";
import ShipmentsArchiveTab from "../components/settings/ShipmentsArchiveTab";
import ChatSettingsTab from "../components/settings/ChatSettingsTab";
import CompanySettingsTab from "../components/settings/CompanySettingsTab";
import ProductionSettingsTab from "../components/settings/ProductionSettingsTab";
import WarehouseSettingsTab from "../components/settings/WarehouseSettingsTab";
import MaterialsSettingsTab from "../components/settings/MaterialsSettingsTab";
import CostingSettingsTab from "../components/settings/CostingSettingsTab";
import BackupSettingsTab from "../components/settings/BackupSettingsTab";
import SuperAdminHubTab from "../components/settings/SuperAdminHubTab";
import MenuVisibilityTab from "../components/settings/MenuVisibilityTab";
import DashboardWidgetsTab from "../components/settings/DashboardWidgetsTab";
import ProductionStagesManagerTab from "../components/settings/ProductionStagesManagerTab";
import SystemLogsTab from "../components/settings/SystemLogsTab";
import MobileAppSettingsTab from "../components/settings/MobileAppSettingsTab";

const TAB_CONTENT = {
  company: CompanySettingsTab,
  production: ProductionSettingsTab,
  telegram: TelegramTab,
  warehouse: WarehouseSettingsTab,
  materials: MaterialsSettingsTab,
  costing: CostingSettingsTab,
  appearance: AppearanceTab,
  backupSettings: BackupSettingsTab,
  superAdmin: SuperAdminHubTab,
  menuVisibility: MenuVisibilityTab,
  dashboardWidgets: DashboardWidgetsTab,
  productionStages: ProductionStagesManagerTab,
  systemLogs: SystemLogsTab,
  mobileApp: MobileAppSettingsTab,
  users: UsersTab,
  permissions: PermissionsTab,
  notifications: NotificationsTab,
  orders: OrdersTab,
  shipments: ShipmentsArchiveTab,
  search: SearchTab,
  online: OnlineTab,
  chat: ChatSettingsTab,
  audit: AuditTab,
  migration: MigrationTab,
  backup: BackupTab,
};

export default function SettingsPage() {
  const { t } = useLocale();
  const [tab, setTab] = useState("superAdmin");
  const ActivePanel = TAB_CONTENT[tab] || CompanySettingsTab;

  return (
    <AdminRoute>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
      <SettingsLayout activeTab={tab} onTabChange={setTab}>
        {tab === "superAdmin" ? (
          <SuperAdminHubTab onNavigate={setTab} />
        ) : (
          <ActivePanel />
        )}
      </SettingsLayout>
    </AdminRoute>
  );
}
