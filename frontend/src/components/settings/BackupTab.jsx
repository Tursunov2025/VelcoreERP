import { useState } from "react";
import { api, authenticatedFetch } from "../../api/client";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";
import LocalizedFileInput from "../ui/LocalizedFileInput";

export default function BackupTab() {
  const { t } = useLocale();
  const [toast, setToast] = useState("");
  const [importing, setImporting] = useState(false);

  const exportDb = async () => {
    try {
      const res = await authenticatedFetch("/admin/backup/export");
      if (!res.ok) throw new Error(t("legacySettings.backupFailed"));
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `azmus_backup_${Date.now()}.db`;
      link.click();
      URL.revokeObjectURL(link.href);
      setToast(t("legacySettings.backupDownloaded"));
    } catch (e) {
      setToast(e.message);
    }
  };

  const importDb = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      await api.adminImportBackup(file);
      setToast(t("legacySettings.backupImported"));
    } catch (err) {
      setToast(err.message);
    } finally {
      setImporting(false);
    }
  };

  const exportSettings = async () => {
    try {
      const bundle = await api.adminExportSettings(true);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `velcore_settings_${Date.now()}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      setToast(t("legacySettings.settingsExported"));
    } catch (e) {
      setToast(e.message);
    }
  };

  const importSettings = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const text = await file.text();
      const bundle = JSON.parse(text);
      await api.adminImportSettings({
        settings: bundle.settings || bundle,
        merge: true,
      });
      setToast(t("legacySettings.settingsImported"));
    } catch (err) {
      setToast(err.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="pb-8">
      <h2 className="mb-4 text-xl font-black">{t("legacySettings.backupFile")}</h2>
      <div className="space-y-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div>
          <h3 className="font-bold">{t("legacySettings.databaseExport")}</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            {t("legacySettings.databaseExportDescription")}
          </p>
          <button
            type="button"
            onClick={exportDb}
            className="min-h-[48px] w-full rounded-xl bg-black px-6 py-3 font-bold text-white sm:w-auto"
          >
            {t("legacySettings.exportDatabase")}
          </button>
        </div>
        <hr />
        <div>
          <h3 className="font-bold">{t("legacySettings.databaseImport")}</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            {t("legacySettings.databaseImportDescription")}
          </p>
          <LocalizedFileInput accept=".db" onChange={importDb} disabled={importing} />
        </div>
        <hr />
        <div>
          <h3 className="font-bold">{t("legacySettings.settingsJson")}</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            {t("legacySettings.settingsJsonDescription")}
          </p>
          <button
            type="button"
            onClick={exportSettings}
            className="mb-3 min-h-[48px] w-full rounded-xl border px-6 py-3 font-bold sm:w-auto"
          >
            {t("legacySettings.exportSettings")}
          </button>
          <LocalizedFileInput
            accept=".json,application/json"
            onChange={importSettings}
            disabled={importing}
          />
        </div>
        <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
          {t("legacySettings.backupNotice")}
        </div>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
