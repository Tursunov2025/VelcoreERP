import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "company_name", label: "Kompaniya nomi" },
  { key: "company_phone", label: "Telefon" },
  { key: "company_email", label: "Email" },
  { key: "company_address", label: "Manzil" },
  { key: "company_tax_id", label: "STIR / INN" },
  { key: "company_currency", label: "Valyuta belgisi" },
];

export default function CompanySettingsTab() {
  return (
    <DomainSettingsForm
      title="Kompaniya sozlamalari"
      subtitle="Kompaniya profili va aloqa ma'lumotlari"
      fields={FIELDS}
      loadSettings={api.adminGetCompanySettings}
      saveSettings={api.adminUpdateCompanySettings}
    />
  );
}
