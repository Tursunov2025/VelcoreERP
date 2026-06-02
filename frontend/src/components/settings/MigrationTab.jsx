import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import Toast from "../ui/Toast";

const DEFAULT_OPTIONS = {
  include_database: true,
  include_llp_files: true,
  include_branding_files: true,
  include_tasks: true,
  include_permissions: true,
  include_notification_settings: true,
  include_telegram_settings: true,
  label: "local",
};

function ExportReport({ report }) {
  if (!report) return null;
  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm">
      <h4 className="mb-2 font-bold">Eksport hisoboti</h4>
      <ul className="grid gap-1 sm:grid-cols-2">
        <li>Baza hajmi: {report.database_size_kb} KB</li>
        <li>Jadvallar: {report.table_count}</li>
        <li>Vazifalar: {report.tasks_count}</li>
        <li>LLP hujjatlar (DB): {report.llp_documents_count}</li>
        <li>LLP fayllar: {report.llp_files_count}</li>
        <li>Branding fayllar: {report.branding_files_count}</li>
        <li>Branding sozlamalar: {report.brand_settings_count}</li>
        <li>Telegram sozlamalar: {report.telegram_settings_count}</li>
      </ul>
      <p className="mt-2 text-xs text-gray-600 break-all">Baza: {report.database_path}</p>
      <p className="text-xs text-gray-600 break-all">Uploads: {report.upload_root}</p>
    </div>
  );
}

function PreviewTable({ preview }) {
  if (!preview) return null;
  const rows = [
    ["Vazifalar", preview.incoming?.tasks, preview.current?.tasks],
    ["Ruxsatlar", preview.incoming?.permissions, preview.current?.permissions],
    ["LLP hujjatlar (DB)", preview.incoming?.documents, preview.current?.documents],
    ["LLP fayllar", preview.incoming?.llp_files, preview.current?.llp_files],
    ["Branding fayllar", preview.incoming?.branding_files, preview.current?.branding_files],
    ["Branding sozlamalar", preview.incoming?.brand_settings, "—"],
    ["Telegram sozlamalar", preview.incoming?.telegram_settings, "—"],
    ["Bildirishnomalar", preview.incoming?.notification_settings, "—"],
  ];

  return (
    <div className="overflow-x-auto rounded-xl border bg-gray-50 p-4 text-sm">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-gray-500">
            <th className="pb-2 pr-4">Bo&apos;lim</th>
            <th className="pb-2 pr-4">ZIP ichida</th>
            <th className="pb-2">Hozir (server)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, incoming, current]) => (
            <tr key={label} className="border-b border-gray-100">
              <td className="py-2 pr-4 font-medium">{label}</td>
              <td className="py-2 pr-4">{incoming ?? 0}</td>
              <td className="py-2">{current ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {preview.warnings?.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-amber-800">
          {preview.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function VerificationSummary({ verification }) {
  if (!verification) return null;
  return (
    <div
      className={`rounded-xl border p-4 text-sm ${
        verification.ok ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"
      }`}
    >
      <h4 className="mb-2 font-bold">Tekshiruv hisoboti</h4>
      <ul className="grid gap-1 sm:grid-cols-2">
        <li>Vazifalar: {verification.tasks_count}</li>
        <li>Ruxsatlar: {verification.permissions_count}</li>
        <li>LLP fayllar: {verification.llp_files_count}</li>
        <li>Branding fayllar: {verification.branding_files_count}</li>
        <li>Yo&apos;qolgan fayllar: {verification.missing_files_count}</li>
        <li>Branding kalitlar: {verification.brand_settings_count}</li>
        <li>Telegram sozlamalar: {verification.telegram_settings_count}</li>
        <li>Bildirishnomalar: {verification.notification_settings_count}</li>
      </ul>
      {verification.missing_files_count > 0 && (
        <p className="mt-2 text-amber-900">
          Ba&apos;zi fayl havolalari diskda topilmadi (birinchi 20 ro&apos;yxatda).
        </p>
      )}
    </div>
  );
}

export default function MigrationTab() {
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [toast, setToast] = useState("");
  const [exportReport, setExportReport] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [importPassword, setImportPassword] = useState("");
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState("");
  const [importResult, setImportResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [rollbackPassword, setRollbackPassword] = useState("");
  const [rollingBackId, setRollingBackId] = useState(null);

  const loadHistory = useCallback(async () => {
    try {
      const rows = await api.adminMigrationHistory();
      setHistory(rows);
    } catch (e) {
      setToast(e.message);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const toggle = (key) => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleExport = async () => {
    setExporting(true);
    setExportReport(null);
    try {
      const { blob, exportReport: report } = await api.adminMigrationExport(options);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `velcore_migration_${Date.now()}.zip`;
      link.click();
      URL.revokeObjectURL(url);
      setExportReport(report);
      setToast("Migratsiya ZIP yuklab olindi");
      loadHistory();
    } catch (e) {
      setToast(e.message);
    } finally {
      setExporting(false);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) {
      setToast("Avval ZIP fayl tanlang");
      return;
    }
    setPreviewLoading(true);
    setPreview(null);
    setImportResult(null);
    try {
      const data = await api.adminMigrationPreview(selectedFile);
      setPreview(data);
    } catch (e) {
      setToast(e.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setToast("ZIP fayl tanlang");
      return;
    }
    if (!confirmReplace) {
      setToast("To'liq bazani almashtirishni tasdiqlang");
      return;
    }
    if (!importPassword.trim()) {
      setToast("Admin parolini kiriting");
      return;
    }
    setImporting(true);
    setImportProgress("Tekshiruv...");
    try {
      setImportProgress("Zaxira nusxa olinmoqda...");
      await new Promise((r) => setTimeout(r, 300));
      setImportProgress("Import qilinmoqda...");
      const result = await api.adminMigrationImport(selectedFile, importPassword);
      setImportResult(result);
      setImportProgress("Tugadi");
      setToast(result.message || "Import muvaffaqiyatli");
      setImportPassword("");
      setConfirmReplace(false);
      loadHistory();
    } catch (e) {
      setToast(e.message);
      setImportProgress("");
    } finally {
      setImporting(false);
    }
  };

  const handleRollback = async (id) => {
    if (!rollbackPassword.trim()) {
      setToast("Rollback uchun admin parolini kiriting");
      return;
    }
    setRollingBackId(id);
    try {
      const result = await api.adminMigrationRollback(id, rollbackPassword);
      setImportResult(result);
      setToast(result.message || "Rollback bajarildi");
      loadHistory();
    } catch (e) {
      setToast(e.message);
    } finally {
      setRollingBackId(null);
    }
  };

  const optionLabels = [
    ["include_database", "SQLite bazasi"],
    ["include_llp_files", "LLP fayllar"],
    ["include_branding_files", "Branding fayllar"],
    ["include_tasks", "Vazifalar (DB)"],
    ["include_permissions", "Ruxsatlar (DB)"],
    ["include_notification_settings", "Bildirishnomalar (DB)"],
    ["include_telegram_settings", "Telegram (DB)"],
  ];

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">Migratsiya</h2>
      <p className="mb-6 text-sm text-gray-500">
        Local muhitdan eksport qiling, production serverda import qiling. Oxirgi 20 ta zaxira
        saqlanadi.
      </p>

      <div className="mb-8 space-y-4 rounded-2xl border bg-white p-6">
        <h3 className="font-bold">Eksport (manba muhit)</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          {optionLabels.map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={options[key]}
                onChange={() => toggle(key)}
                disabled={key === "include_database"}
              />
              {label}
            </label>
          ))}
        </div>
        <input
          type="text"
          className="w-full max-w-md rounded-xl border px-3 py-2 text-sm"
          placeholder="Muhit nomi (masalan: local)"
          value={options.label}
          onChange={(e) => setOptions((p) => ({ ...p, label: e.target.value }))}
        />
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="rounded-2xl bg-black px-6 py-3 text-white disabled:opacity-50"
        >
          {exporting ? "Eksport..." : "ZIP eksport"}
        </button>
        {exportReport && <ExportReport report={exportReport} />}
      </div>

      <div className="mb-8 space-y-4 rounded-2xl border bg-white p-6">
        <h3 className="font-bold">Import (production)</h3>
        <input
          type="file"
          accept=".zip,application/zip"
          onChange={(e) => {
            setSelectedFile(e.target.files?.[0] || null);
            setPreview(null);
            setImportResult(null);
          }}
        />
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handlePreview}
            disabled={previewLoading || !selectedFile}
            className="rounded-2xl border px-5 py-2 text-sm font-semibold disabled:opacity-50"
          >
            {previewLoading ? "Ko'rib chiqilmoqda..." : "Oldindan ko'rish"}
          </button>
        </div>

        {preview && (
          <div>
            <h4 className="mb-2 font-semibold">Preview</h4>
            <PreviewTable preview={preview} />
          </div>
        )}

        <div className="space-y-3 rounded-xl bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900">
            To&apos;liq bazani almashtirish (Full DB Replace)
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmReplace}
              onChange={(e) => setConfirmReplace(e.target.checked)}
            />
            Production ma&apos;lumotlari almashtirilishini tushundim
          </label>
          <input
            type="password"
            className="w-full max-w-sm rounded-xl border px-3 py-2 text-sm"
            placeholder="Admin paroli (tasdiqlash)"
            value={importPassword}
            onChange={(e) => setImportPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={handleImport}
            disabled={importing || !selectedFile}
            className="rounded-2xl bg-red-700 px-6 py-3 text-white disabled:opacity-50"
          >
            {importing ? "Import..." : "Import qilish"}
          </button>
          {importProgress && (
            <div className="text-sm text-gray-600">
              <div className="mb-1 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                <div
                  className="h-full animate-pulse bg-black transition-all"
                  style={{ width: importing ? "70%" : "100%" }}
                />
              </div>
              {importProgress}
            </div>
          )}
        </div>

        {importResult?.verification && (
          <VerificationSummary verification={importResult.verification} />
        )}
        {importResult?.restart_required && (
          <p className="text-sm font-medium text-amber-800">
            API ni qayta ishga tushiring (Render: Manual Deploy yoki Restart).
          </p>
        )}
      </div>

      <div className="rounded-2xl border bg-white p-6">
        <h3 className="mb-4 font-bold">Migratsiya tarixi</h3>
        <input
          type="password"
          className="mb-4 w-full max-w-sm rounded-xl border px-3 py-2 text-sm"
          placeholder="Rollback uchun admin paroli"
          value={rollbackPassword}
          onChange={(e) => setRollbackPassword(e.target.value)}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-gray-500">
                <th className="pb-2 pr-3">ID</th>
                <th className="pb-2 pr-3">Amal</th>
                <th className="pb-2 pr-3">Holat</th>
                <th className="pb-2 pr-3">Fayl</th>
                <th className="pb-2 pr-3">Sana</th>
                <th className="pb-2">Rollback</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id} className="border-b border-gray-100">
                  <td className="py-2 pr-3">{row.id}</td>
                  <td className="py-2 pr-3">{row.action}</td>
                  <td className="py-2 pr-3">{row.status}</td>
                  <td className="py-2 pr-3 max-w-[120px] truncate">{row.bundle_name}</td>
                  <td className="py-2 pr-3">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="py-2">
                    {row.action === "import" && row.status === "completed" && (
                      <button
                        type="button"
                        disabled={rollingBackId === row.id}
                        onClick={() => handleRollback(row.id)}
                        className="text-xs font-semibold text-red-700 underline disabled:opacity-50"
                      >
                        {rollingBackId === row.id ? "..." : "Rollback"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-4 text-gray-400">
                    Tarix bo&apos;sh
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
