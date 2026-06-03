import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "auto_backup_enabled", label: "Avto backup (true/false)" },
  { key: "auto_backup_interval_hours", label: "Avto backup interval (soat)" },
  { key: "backup_retention_count", label: "Saqlash soni (migratsiya)" },
  { key: "backup_include_uploads", label: "Uploads bilan eksport (true/false)" },
  {
    key: "migration_include_settings",
    label: "Migratsiyada sozlamalar (true/false)",
  },
  { key: "jwt_access_minutes", label: "JWT access (daqiqa)" },
  { key: "jwt_refresh_days", label: "JWT refresh (kun)" },
];

export default function BackupSettingsTab() {
  return (
    <DomainSettingsForm
      title="Backup sozlamalari"
      subtitle="Avtomatik backup, migratsiya va JWT"
      fields={FIELDS}
      loadSettings={api.adminGetBackupSettings}
      saveSettings={api.adminUpdateBackupSettings}
    />
  );
}
