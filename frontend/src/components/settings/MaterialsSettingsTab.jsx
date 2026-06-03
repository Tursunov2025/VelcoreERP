import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "materials_default_unit", label: "Default birlik" },
  { key: "materials_low_stock_default", label: "Default minimal qoldiq" },
  {
    key: "materials_auto_consume_enabled",
    label: "Avtomatik sarflash (true/false)",
  },
  {
    key: "materials_auto_consume_stages_json",
    label: "Avto-sarflash bosqichlari (JSON)",
    type: "textarea",
    hint: '["Lazer","Kraska"]',
  },
  {
    key: "materials_categories_json",
    label: "Material kategoriyalari (JSON)",
    type: "textarea",
    hint: '[["METAL","Metall"],["PAINT","Bo\'yoq"]]',
  },
];

export default function MaterialsSettingsTab() {
  return (
    <DomainSettingsForm
      title="Xom ashyo sozlamalari"
      subtitle="Material ombori va avtomatik sarflash"
      fields={FIELDS}
      loadSettings={api.adminGetMaterialsSettings}
      saveSettings={api.adminUpdateMaterialsSettings}
    />
  );
}
