import { api } from "../../api/client";
import DomainSettingsForm from "./DomainSettingsForm";

const FIELDS = [
  { key: "auto_backup_enabled" },
  { key: "auto_backup_interval_hours" },
  { key: "backup_retention_count" },
  { key: "backup_include_uploads" },
  {
    key: "migration_include_settings",
  },
  { key: "jwt_access_minutes" },
  { key: "jwt_refresh_days" },
];

export default function BackupSettingsTab() {
  return (
    <DomainSettingsForm
      title="legacySettings.backupSettingsTitle"
      subtitle="legacySettings.backupSettingsDescription"
      fields={FIELDS}
      loadSettings={api.adminGetBackupSettings}
      saveSettings={api.adminUpdateBackupSettings}
    />
  );
}
