import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "company_name" }, { key: "company_phone" }, { key: "company_email" },
  { key: "company_address" }, { key: "company_tax_id" }, { key: "company_currency" },
];

export default function CompanySettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.companyTitle"
      subtitle="legacySettings.companyDescription"
      fields={FIELDS}
      loadSettings={api.adminGetCompanySettings}
      saveSettings={api.adminUpdateCompanySettings}
    />
  );
}
