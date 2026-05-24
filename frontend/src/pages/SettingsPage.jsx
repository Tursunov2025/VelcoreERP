import { useState } from "react";
import AdminRoute from "../components/layout/AdminRoute";
import PageHeader from "../components/ui/PageHeader";
import SettingsLayout from "../components/settings/SettingsLayout";
import UsersTab from "../components/settings/UsersTab";
import OrdersTab from "../components/settings/OrdersTab";
import SearchTab from "../components/settings/SearchTab";
import SystemTab from "../components/settings/SystemTab";
import OnlineTab from "../components/settings/OnlineTab";
import AuditTab from "../components/settings/AuditTab";
import BackupTab from "../components/settings/BackupTab";
import ShipmentsArchiveTab from "../components/settings/ShipmentsArchiveTab";
import ChatSettingsTab from "../components/settings/ChatSettingsTab";

const TAB_CONTENT = {
  users: UsersTab,
  orders: OrdersTab,
  shipments: ShipmentsArchiveTab,
  search: SearchTab,
  online: OnlineTab,
  chat: ChatSettingsTab,
  system: SystemTab,
  audit: AuditTab,
  backup: BackupTab,
};

export default function SettingsPage() {
  const [tab, setTab] = useState("users");
  const ActivePanel = TAB_CONTENT[tab] || UsersTab;

  return (
    <AdminRoute>
      <PageHeader
        title="Admin sozlamalari"
        subtitle="Foydalanuvchilar, zakazlar, tizim va backup boshqaruvi"
      />
      <SettingsLayout activeTab={tab} onTabChange={setTab}>
        <ActivePanel />
      </SettingsLayout>
    </AdminRoute>
  );
}
