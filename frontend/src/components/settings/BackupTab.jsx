import { useState } from "react";
import { api, authenticatedFetch } from "../../api/client";
import Toast from "../ui/Toast";

export default function BackupTab() {
  const [toast, setToast] = useState("");
  const [importing, setImporting] = useState(false);

  const exportDb = async () => {
    try {
      const res = await authenticatedFetch("/admin/backup/export");
      if (!res.ok) throw new Error("Backup failed");
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `azmus_backup_${Date.now()}.db`;
      link.click();
      URL.revokeObjectURL(link.href);
      setToast("Backup yuklab olindi");
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
      setToast("Backup import qilindi. API ni qayta ishga tushiring.");
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
      setToast("Sozlamalar JSON eksport qilindi");
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
      setToast("Sozlamalar import qilindi");
    } catch (err) {
      setToast(err.message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="pb-8">
      <h2 className="mb-4 text-xl font-black">Backup fayl</h2>
      <div className="space-y-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        <div>
          <h3 className="font-bold">Baza eksport</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            SQLite bazasini fayl sifatida yuklab oling
          </p>
          <button
            type="button"
            onClick={exportDb}
            className="min-h-[48px] w-full rounded-xl bg-black px-6 py-3 font-bold text-white sm:w-auto"
          >
            Bazani eksport qilish
          </button>
        </div>
        <hr />
        <div>
          <h3 className="font-bold">Baza import</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            Backup faylni tiklash (avvalgi nusxa saqlanadi)
          </p>
          <input type="file" accept=".db" onChange={importDb} disabled={importing} className="w-full" />
        </div>
        <hr />
        <div>
          <h3 className="font-bold">Sozlamalar JSON</h3>
          <p className="mb-3 text-sm text-[var(--brand-muted)]">
            Markaziy sozlamalarni alohida eksport/import (migratsiya ZIP ichida ham bor)
          </p>
          <button
            type="button"
            onClick={exportSettings}
            className="mb-3 min-h-[48px] w-full rounded-xl border px-6 py-3 font-bold sm:w-auto"
          >
            Sozlamalarni eksport
          </button>
          <input
            type="file"
            accept=".json,application/json"
            onChange={importSettings}
            disabled={importing}
            className="w-full"
          />
        </div>
        <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
          Avtomatik backup va JWT sozlamalari &quot;Backup&quot; markaziy bo&apos;limida. To&apos;liq migratsiya ZIP uchun Migratsiya bo&apos;limiga o&apos;ting.
        </div>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
