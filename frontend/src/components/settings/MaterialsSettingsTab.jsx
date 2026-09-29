import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "materials_default_unit" },
  { key: "materials_low_stock_default" },
  {
    key: "materials_auto_consume_enabled",
  },
  {
    key: "materials_auto_consume_stages_json",
    type: "textarea",
    hint: '["Lazer","Kraska"]',
  },
  {
    key: "materials_categories_json",
    type: "textarea",
    hint: '[["METAL","Metall"],["PAINT","Bo\'yoq"]]',
  },
];

export default function MaterialsSettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.materialsTitle"
      subtitle="legacySettings.materialsDescription"
      fields={FIELDS}
      loadSettings={api.adminGetMaterialsSettings}
      saveSettings={api.adminUpdateMaterialsSettings}
    />
  );
}
