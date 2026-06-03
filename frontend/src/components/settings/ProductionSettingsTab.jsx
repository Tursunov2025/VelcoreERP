import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  {
    key: "production_stages_json",
    label: "Ishlab chiqarish bosqichlari (JSON)",
    type: "textarea",
    hint: 'Masalan: ["Kesish","Svarka","Kraska"]',
  },
  {
    key: "departments_json",
    label: "Bo'limlar (JSON)",
    type: "textarea",
    hint: 'Masalan: ["Kesish","Svarka","Ombor"]',
  },
  {
    key: "mes_job_default_priority",
    label: "MES ish default prioriteti",
    placeholder: "normal",
  },
  { key: "mes_inspection_stage", label: "Tekshiruv bosqichi nomi" },
  { key: "mes_final_stage", label: "Tayyor bosqichi nomi" },
  {
    key: "mes_default_stages_json",
    label: "MES default marshrut bosqichlari (JSON)",
    type: "textarea",
    hint: '[["Lazer","Kesish"],["Kraska","Kraska"]]',
  },
];

export default function ProductionSettingsTab() {
  return (
    <DomainSettingsForm
      title="Ishlab chiqarish sozlamalari"
      subtitle="Bosqichlar, bo'limlar va MES default qiymatlar"
      fields={FIELDS}
      loadSettings={api.adminGetProductionSettings}
      saveSettings={api.adminUpdateProductionSettings}
    />
  );
}
