import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "costing_currency", label: "Valyuta kodi" },
  { key: "costing_currency_symbol", label: "Valyuta belgisi" },
  { key: "costing_default_markup_pct", label: "Default ustama (%)" },
  {
    key: "costing_track_job_material_cost",
    label: "Ish material narxini kuzatish (true/false)",
  },
];

export default function CostingSettingsTab() {
  return (
    <DomainSettingsForm
      title="Tannarx sozlamalari"
      subtitle="Material narxi va ish costing"
      fields={FIELDS}
      loadSettings={api.adminGetCostingSettings}
      saveSettings={api.adminUpdateCostingSettings}
    />
  );
}
