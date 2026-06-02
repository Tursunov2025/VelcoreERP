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
import SystemTab from "../components/settings/SystemTab";
import OnlineTab from "../components/settings/OnlineTab";
import AuditTab from "../components/settings/AuditTab";
import BackupTab from "../components/settings/BackupTab";
import MigrationTab from "../components/settings/MigrationTab";
import ShipmentsArchiveTab from "../components/settings/ShipmentsArchiveTab";
import ChatSettingsTab from "../components/settings/ChatSettingsTab";

const TAB_CONTENT = {
  users: UsersTab,
  appearance: AppearanceTab,
  permissions: PermissionsTab,
  telegram: TelegramTab,
  notifications: NotificationsTab,
  orders: OrdersTab,
  shipments: ShipmentsArchiveTab,
  search: SearchTab,
  online: OnlineTab,
  chat: ChatSettingsTab,
  system: SystemTab,
  audit: AuditTab,
  migration: MigrationTab,
  backup: BackupTab,
};

export default function SettingsPage() {
  const { t } = useLocale();
  const [tab, setTab] = useState("users");
  const ActivePanel = TAB_CONTENT[tab] || UsersTab;

  return (
    <AdminRoute>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
      <SettingsLayout activeTab={tab} onTabChange={setTab}>
        <ActivePanel />
      </SettingsLayout>
    </AdminRoute>
  );
}
