import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "warehouse_low_stock_alerts" },
  { key: "warehouse_finished_goods_prefix" },
  {
    key: "warehouse_dispatch_requires_approval",
  },
  {
    key: "warehouse_default_receipt_notes",
    type: "textarea",
  },
];

export default function WarehouseSettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.warehouseTitle"
      subtitle="legacySettings.warehouseDescription"
      fields={FIELDS}
      loadSettings={api.adminGetWarehouseSettings}
      saveSettings={api.adminUpdateWarehouseSettings}
    />
  );
}
