import { useState } from "react";
import { api, API_BASE } from "../../api/client";
import Toast from "../ui/Toast";

export default function BackupTab() {
  const [toast, setToast] = useState("");
  const [importing, setImporting] = useState(false);

  const exportDb = () => {
    const tokens = JSON.parse(localStorage.getItem("azmus_tokens") || "{}");
    const url = `${API_BASE}/admin/backup/export`;
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "");
    fetch(url, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = `azmus_backup_${Date.now()}.db`;
        link.click();
        URL.revokeObjectURL(objectUrl);
        setToast("Backup yuklab olindi");
      })
      .catch((e) => setToast(e.message));
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

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">Backup</h2>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
        <div>
          <h3 className="font-bold">Eksport</h3>
          <p className="mb-3 text-sm text-gray-500">
            SQLite bazasini fayl sifatida yuklab oling
          </p>
          <button
            type="button"
            onClick={exportDb}
            className="rounded-2xl bg-black px-6 py-3 text-white"
          >
            Bazani eksport qilish
          </button>
        </div>
        <hr />
        <div>
          <h3 className="font-bold">Import</h3>
          <p className="mb-3 text-sm text-gray-500">
            Backup faylni tiklash (avvalgi nusxa saqlanadi)
          </p>
          <input
            type="file"
            accept=".db"
            onChange={importDb}
            disabled={importing}
          />
        </div>
        <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
          Avtomatik backup sozlamalari Tizim bo&apos;limida
        </div>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
