import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  {
    key: "production_stages_json",
    type: "textarea",
    hint: 'Masalan: ["Kesish","Svarka","Kraska"]',
  },
  {
    key: "departments_json",
    type: "textarea",
    hint: 'Masalan: ["Kesish","Svarka","Ombor"]',
  },
  {
    key: "mes_job_default_priority",

    placeholder: "normal",
  },
  { key: "mes_inspection_stage" },
  { key: "mes_final_stage" },
  {
    key: "mes_default_stages_json",
    type: "textarea",
    hint: '[["Lazer","Kesish"],["Kraska","Kraska"]]',
  },
];

export default function ProductionSettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.productionTitle"
      subtitle="legacySettings.productionDescription"
      fields={FIELDS}
      loadSettings={api.adminGetProductionSettings}
      saveSettings={api.adminUpdateProductionSettings}
    />
  );
}
