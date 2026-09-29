import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";
import LocalizedFileInput from "../ui/LocalizedFileInput";

const DEFAULT_OPTIONS = {
  include_database: true,
  include_llp_files: true,
  include_branding_files: true,
  include_mes_files: true,
  include_tasks: true,
  include_permissions: true,
  include_notification_settings: true,
  include_telegram_settings: true,
  label: "local",
};

function MesDiagnostics({ diagnostics, t }) {
  if (!diagnostics || typeof diagnostics !== "object") return null;
  const entries = Object.entries(diagnostics);
  if (!entries.length) return null;
  return (
    <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50 p-3">
      <h5 className="mb-2 text-xs font-bold uppercase tracking-wide text-blue-900">{t("legacySettings.migration.diagnostics")}</h5>
      <ul className="grid gap-1 text-sm sm:grid-cols-2">
        {entries.map(([label, value]) => (
          <li key={label}>
            {label}: <strong>{value ?? 0}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExportReport({ report, t }) {
  if (!report) return null;
  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm">
      <h4 className="mb-2 font-bold">{t("legacySettings.migration.exportReport")}</h4>
      <ul className="grid gap-1 sm:grid-cols-2">
        <li>{t("legacySettings.migration.databaseSize")}: {report.database_size_kb} KB</li>
        <li>{t("legacySettings.migration.tables")}: {report.table_count}</li>
        <li>{t("legacySettings.migration.tasks")}: {report.tasks_count}</li>
        <li>{t("legacySettings.migration.llpDocuments")}: {report.llp_documents_count}</li>
        <li>{t("legacySettings.migration.llpFiles")}: {report.llp_files_count}</li>
        <li>{t("legacySettings.migration.brandingFiles")}: {report.branding_files_count}</li>
        <li>{t("legacySettings.migration.mesFiles")}: {report.mes_files_count ?? 0}</li>
        <li>{t("legacySettings.migration.brandingSettings")}: {report.brand_settings_count}</li>
        <li>{t("legacySettings.migration.telegramSettings")}: {report.telegram_settings_count}</li>
      </ul>
      <MesDiagnostics diagnostics={report.mes_diagnostics} t={t} />
      <p className="mt-2 text-xs text-gray-600 break-all">{t("legacySettings.migration.database")}: {report.database_path}</p>
      <p className="text-xs text-gray-600 break-all">{t("legacySettings.migration.uploads")}: {report.upload_root}</p>
    </div>
  );
}

function PreviewTable({ preview, t }) {
  if (!preview) return null;
  const rows = [
    [t("legacySettings.migration.tasks"), preview.incoming?.tasks, preview.current?.tasks],
    [t("legacySettings.migration.permissions"), preview.incoming?.permissions, preview.current?.permissions],
    [t("legacySettings.migration.llpDocuments"), preview.incoming?.documents, preview.current?.documents],
    [t("legacySettings.migration.llpFiles"), preview.incoming?.llp_files, preview.current?.llp_files],
    [t("legacySettings.migration.brandingFiles"), preview.incoming?.branding_files, preview.current?.branding_files],
    [t("legacySettings.migration.mesFiles"), preview.incoming?.mes_files, preview.current?.mes_files],
    [t("legacySettings.migration.mesCategories"), preview.incoming?.mes_categories, preview.current?.mes_categories],
    [t("legacySettings.migration.mesParts"), preview.incoming?.mes_parts, preview.current?.mes_parts],
    [t("legacySettings.migration.mesTemplates"), preview.incoming?.mes_templates, preview.current?.mes_templates],
    ["MES BOM", preview.incoming?.mes_bom_lines, preview.current?.mes_bom_lines],
    [t("legacySettings.migration.mesRoutes"), preview.incoming?.mes_routes, preview.current?.mes_routes],
    [t("legacySettings.migration.mesRouteSteps"), preview.incoming?.mes_route_steps, preview.current?.mes_route_steps],
    [t("legacySettings.migration.mesDrawings"), preview.incoming?.mes_drawings, preview.current?.mes_drawings],
    [t("legacySettings.migration.brandingSettings"), preview.incoming?.brand_settings, "—"],
    [t("legacySettings.migration.telegramSettings"), preview.incoming?.telegram_settings, "—"],
    [t("settingsNav.notifications"), preview.incoming?.notification_settings, "—"],
  ];

  return (
    <div className="overflow-x-auto rounded-xl border bg-gray-50 p-4 text-sm">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-gray-500">
            <th className="pb-2 pr-4">{t("legacySettings.migration.section")}</th>
            <th className="pb-2 pr-4">{t("legacySettings.migration.inZip")}</th>
            <th className="pb-2">{t("legacySettings.migration.currentServer")}</th>
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

function VerificationSummary({ verification, t }) {
  if (!verification) return null;
  return (
    <div
      className={`rounded-xl border p-4 text-sm ${
        verification.ok ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"
      }`}
    >
      <h4 className="mb-2 font-bold">{t("legacySettings.migration.verificationReport")}</h4>
      <ul className="grid gap-1 sm:grid-cols-2">
        <li>{t("legacySettings.migration.tasks")}: {verification.tasks_count}</li>
        <li>{t("legacySettings.migration.permissions")}: {verification.permissions_count}</li>
        <li>{t("legacySettings.migration.llpFiles")}: {verification.llp_files_count}</li>
        <li>{t("legacySettings.migration.brandingFiles")}: {verification.branding_files_count}</li>
        <li>{t("legacySettings.migration.mesFiles")}: {verification.mes_files_count ?? 0}</li>
        <li>{t("legacySettings.migration.missingFiles")}: {verification.missing_files_count}</li>
        <li>{t("legacySettings.migration.brandingKeys")}: {verification.brand_settings_count}</li>
        <li>{t("legacySettings.migration.telegramSettings")}: {verification.telegram_settings_count}</li>
        <li>{t("settingsNav.notifications")}: {verification.notification_settings_count}</li>
      </ul>
      <MesDiagnostics diagnostics={verification.mes_diagnostics} t={t} />
      {verification.missing_files_count > 0 && (
        <p className="mt-2 text-amber-900">
          {t("legacySettings.migration.missingFilesWarning")}
        </p>
      )}
    </div>
  );
}

export default function MigrationTab() {
  const { t } = useLocale();
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
      setToast(t("legacySettings.migration.downloaded"));
      loadHistory();
    } catch (e) {
      setToast(e.message);
    } finally {
      setExporting(false);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) {
      setToast(t("legacySettings.migration.chooseZipFirst"));
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
      setToast(t("legacySettings.migration.chooseZip"));
      return;
    }
    if (!confirmReplace) {
      setToast(t("legacySettings.migration.confirmRequired"));
      return;
    }
    if (!importPassword.trim()) {
      setToast(t("legacySettings.migration.passwordRequired"));
      return;
    }
    setImporting(true);
    setImportProgress(t("legacySettings.migration.checking"));
    try {
      setImportProgress(t("legacySettings.migration.backingUp"));
      await new Promise((r) => setTimeout(r, 300));
      setImportProgress(t("legacySettings.migration.importing"));
      const result = await api.adminMigrationImport(selectedFile, importPassword);
      setImportResult(result);
      setImportProgress(t("legacySettings.migration.completed"));
      setToast(result.message || t("legacySettings.migration.importSuccessful"));
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
      setToast(t("legacySettings.migration.rollbackPasswordRequired"));
      return;
    }
    setRollingBackId(id);
    try {
      const result = await api.adminMigrationRollback(id, rollbackPassword);
      setImportResult(result);
      setToast(result.message || t("legacySettings.migration.rollbackSuccessful"));
      loadHistory();
    } catch (e) {
      setToast(e.message);
    } finally {
      setRollingBackId(null);
    }
  };

  const optionLabels = [
    ["include_database", t("legacySettings.migration.sqliteDatabase")],
    ["include_llp_files", t("legacySettings.migration.llpFiles")],
    ["include_branding_files", t("legacySettings.migration.brandingFiles")],
    ["include_mes_files", t("legacySettings.migration.mesFilesBundle")],
    ["include_tasks", t("legacySettings.migration.tasksDb")],
    ["include_permissions", t("legacySettings.migration.permissionsDb")],
    ["include_notification_settings", t("legacySettings.migration.notificationsDb")],
    ["include_telegram_settings", t("legacySettings.migration.telegramDb")],
  ];

  const historyMesSummary = (row) => {
    try {
      const data = JSON.parse(row.summary_json || "{}");
      const diag =
        data.export_report?.mes_diagnostics ||
        data.verification?.mes_diagnostics ||
        null;
      if (!diag) return null;
      return `MES: ${diag["MES Templates"] ?? 0} shablon, ${diag["MES BOM"] ?? 0} BOM`;
    } catch {
      return null;
    }
  };

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("settingsNav.migration")}</h2>
      <p className="mb-6 text-sm text-gray-500">
        {t("legacySettings.migration.description")}
      </p>

      <div className="mb-8 space-y-4 rounded-2xl border bg-white p-6">
        <h3 className="font-bold">{t("legacySettings.migration.sourceExport")}</h3>
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
          placeholder={t("legacySettings.migration.environmentPlaceholder")}
          value={options.label}
          onChange={(e) => setOptions((p) => ({ ...p, label: e.target.value }))}
        />
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="rounded-2xl bg-black px-6 py-3 text-white disabled:opacity-50"
        >
          {exporting ? t("legacySettings.migration.exporting") : t("legacySettings.migration.exportZip")}
        </button>
        {exportReport && <ExportReport report={exportReport} t={t} />}
      </div>

      <div className="mb-8 space-y-4 rounded-2xl border bg-white p-6">
        <h3 className="font-bold">{t("legacySettings.migration.productionImport")}</h3>
        <LocalizedFileInput
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
            {previewLoading ? t("legacySettings.migration.previewing") : t("platformAdministration.preview")}
          </button>
        </div>

        {preview && (
          <div>
            <h4 className="mb-2 font-semibold">{t("platformAdministration.preview")}</h4>
            <PreviewTable preview={preview} t={t} />
          </div>
        )}

        <div className="space-y-3 rounded-xl bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900">
            {t("legacySettings.migration.fullReplace")}
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmReplace}
              onChange={(e) => setConfirmReplace(e.target.checked)}
            />
            {t("legacySettings.migration.confirmReplace")}
          </label>
          <input
            type="password"
            className="w-full max-w-sm rounded-xl border px-3 py-2 text-sm"
            placeholder={t("legacySettings.migration.adminPassword")}
            value={importPassword}
            onChange={(e) => setImportPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={handleImport}
            disabled={importing || !selectedFile}
            className="rounded-2xl bg-red-700 px-6 py-3 text-white disabled:opacity-50"
          >
            {importing ? t("legacySettings.migration.importing") : t("legacySettings.migration.importAction")}
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
          <VerificationSummary verification={importResult.verification} t={t} />
        )}
        {importResult?.restart_required && (
          <p className="text-sm font-medium text-amber-800">
            {t("legacySettings.migration.restartApi")}
          </p>
        )}
      </div>

      <div className="rounded-2xl border bg-white p-6">
        <h3 className="mb-4 font-bold">{t("legacySettings.migration.history")}</h3>
        <input
          type="password"
          className="mb-4 w-full max-w-sm rounded-xl border px-3 py-2 text-sm"
          placeholder={t("legacySettings.migration.rollbackPassword")}
          value={rollbackPassword}
          onChange={(e) => setRollbackPassword(e.target.value)}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-gray-500">
                <th className="pb-2 pr-3">{t("legacySettings.migration.id")}</th>
                <th className="pb-2 pr-3">{t("platformAdministration.action")}</th>
                <th className="pb-2 pr-3">{t("common.status")}</th>
                <th className="pb-2 pr-3">{t("legacySettings.migration.file")}</th>
                <th className="pb-2 pr-3">{t("legacySettings.migration.date")}</th>
                <th className="pb-2 pr-3">MES</th>
                <th className="pb-2">{t("legacySettings.migration.rollback")}</th>
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
                  <td className="py-2 pr-3 text-xs text-gray-500">
                    {historyMesSummary(row) || "—"}
                  </td>
                  <td className="py-2">
                    {row.action === "import" && row.status === "completed" && (
                      <button
                        type="button"
                        disabled={rollingBackId === row.id}
                        onClick={() => handleRollback(row.id)}
                        className="text-xs font-semibold text-red-700 underline disabled:opacity-50"
                      >
                        {rollingBackId === row.id ? "…" : t("legacySettings.migration.rollback")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-4 text-gray-400">
                    {t("legacySettings.migration.emptyHistory")}
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
