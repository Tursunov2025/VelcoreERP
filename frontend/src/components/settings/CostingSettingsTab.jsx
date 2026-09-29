import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "costing_currency" }, { key: "costing_currency_symbol" }, { key: "costing_default_markup_pct" },
  {
    key: "costing_track_job_material_cost",
  },
];

export default function CostingSettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.costingTitle"
      subtitle="legacySettings.costingDescription"
      fields={FIELDS}
      loadSettings={api.adminGetCostingSettings}
      saveSettings={api.adminUpdateCostingSettings}
    />
  );
}
