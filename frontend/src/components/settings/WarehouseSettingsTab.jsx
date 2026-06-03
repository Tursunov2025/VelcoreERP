import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "warehouse_low_stock_alerts", label: "Kam qoldiq ogohlantirish (true/false)" },
  { key: "warehouse_finished_goods_prefix", label: "Tayyor mahsulot lokatsiya prefiksi" },
  {
    key: "warehouse_dispatch_requires_approval",
    label: "Yuk chiqarish tasdiqi (true/false)",
  },
  {
    key: "warehouse_default_receipt_notes",
    label: "Default qabul izohi",
    type: "textarea",
  },
];

export default function WarehouseSettingsTab() {
  return (
    <DomainSettingsForm
      title="Ombor sozlamalari"
      subtitle="Tayyor mahsulot ombori va ogohlantirishlar"
      fields={FIELDS}
      loadSettings={api.adminGetWarehouseSettings}
      saveSettings={api.adminUpdateWarehouseSettings}
    />
  );
}
