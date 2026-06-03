import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

const BRANDS = ["Zebra", "TSC", "XPrinter", "Godex", "Generic"];
const CONNECTION_TYPES = [
  { id: "cloud_agent", label: "Cloud Agent (USB / Windows)" },
  { id: "network", label: "Network (IP / ZPL)" },
];

const emptyPrinter = () => ({
  name: "",
  brand: "XPrinter",
  connection_type: "cloud_agent",
  ip_address: "",
  port: 9100,
  windows_printer_name: "",
  auto_print_enabled: false,
});

function fmtDate(v) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
}

export default function LabelPrintersSettingsTab() {
  const { t } = useLocale();
  const [printers, setPrinters] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  const load = () => {
    setLoading(true);
    Promise.all([api.adminGetLabelPrinters(), api.adminPrintingDashboard().catch(() => null)])
      .then(([data, dash]) => {
        setPrinters(data?.printers?.length ? data.printers : [emptyPrinter()]);
        setDashboard(dash);
      })
      .catch((e) => setToast(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const updateRow = (idx, field, value) => {
    setPrinters((rows) =>
      rows.map((row, i) => (i === idx ? { ...row, [field]: value } : row))
    );
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = printers.map((p) => ({
        name: (p.name || p.printer_name || "").trim(),
        brand: p.brand || "XPrinter",
        connection_type: p.connection_type || "cloud_agent",
        ip_address: (p.ip_address || "").trim(),
        port: Number(p.port) || 9100,
        windows_printer_name: (p.windows_printer_name || p.name || "").trim(),
        auto_print_enabled: Boolean(p.auto_print_enabled),
      }));
      await api.adminSaveLabelPrinters(payload);
      setToast(t("controlCenter.saved"));
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  const retryJob = async (jobId) => {
    try {
      await api.adminRetryPrintJob(jobId);
      setToast(t("printing.retryQueued"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  if (loading && !dashboard) {
    return <p className="text-sm text-[var(--brand-muted)]">{t("common.loading")}</p>;
  }

  const dashPrinters = dashboard?.printers || [];
  const totals = dashboard?.totals || {};

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border bg-white p-4">
          <p className="text-xs text-[var(--brand-muted)]">{t("printing.queue")}</p>
          <p className="text-2xl font-black">{totals.pending ?? 0}</p>
        </div>
        <div className="rounded-2xl border bg-white p-4">
          <p className="text-xs text-[var(--brand-muted)]">{t("printing.printing")}</p>
          <p className="text-2xl font-black">{totals.printing ?? 0}</p>
        </div>
        <div className="rounded-2xl border bg-white p-4">
          <p className="text-xs text-[var(--brand-muted)]">{t("printing.failed")}</p>
          <p className="text-2xl font-black">{totals.failed ?? 0}</p>
        </div>
        <div className="rounded-2xl border bg-white p-4">
          <p className="text-xs text-[var(--brand-muted)]">{t("printing.completedToday")}</p>
          <p className="text-2xl font-black">{totals.completed_today ?? 0}</p>
        </div>
      </div>

      {dashPrinters.length > 0 ? (
        <div className="rounded-2xl border bg-gray-50 p-4">
          <h3 className="mb-3 font-bold">{t("printing.agentStatus")}</h3>
          <div className="space-y-2">
            {dashPrinters.map((p) => (
              <div
                key={p.name}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-white px-4 py-3 text-sm"
              >
                <div>
                  <span className="font-semibold">{p.name}</span>
                  <span
                    className={`ml-2 rounded-full px-2 py-0.5 text-xs font-bold ${
                      p.online ? "bg-green-100 text-green-800" : "bg-gray-200 text-gray-700"
                    }`}
                  >
                    {p.online ? t("printing.online") : t("printing.offline")}
                  </span>
                </div>
                <div className="text-[var(--brand-muted)]">
                  {t("printing.queue")}: {p.queue_count} · {t("printing.failed")}: {p.failed_count}
                </div>
                <div className="text-xs text-[var(--brand-muted)]">
                  {t("printing.lastPrint")}: {fmtDate(p.last_print_at)} ({p.last_print_label || "—"})
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {(dashboard?.failed_jobs || []).length > 0 ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
          <h3 className="mb-2 font-bold text-red-900">{t("printing.failedJobs")}</h3>
          <ul className="space-y-2">
            {dashboard.failed_jobs.map((j) => (
              <li
                key={j.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-3 py-2 text-sm"
              >
                <span className="font-mono">{j.label_code}</span>
                <span className="text-red-700">{j.error_message || "—"}</span>
                <button
                  type="button"
                  onClick={() => retryJob(j.id)}
                  className="rounded-lg border px-3 py-1 text-xs font-bold"
                >
                  {t("printing.retry")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="text-sm text-[var(--brand-muted)]">{t("traceability.printersHelp")}</p>
      {printers.map((p, idx) => (
        <div key={idx} className="rounded-2xl border bg-white p-4 shadow-sm">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-semibold">{t("traceability.printerName")}</span>
              <input
                className="mt-1 w-full rounded-xl border px-3 py-2"
                value={p.name || ""}
                onChange={(e) => updateRow(idx, "name", e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="font-semibold">{t("printing.connectionType")}</span>
              <select
                className="mt-1 w-full rounded-xl border px-3 py-2"
                value={p.connection_type || "cloud_agent"}
                onChange={(e) => updateRow(idx, "connection_type", e.target.value)}
              >
                {CONNECTION_TYPES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-semibold">{t("traceability.printerBrand")}</span>
              <select
                className="mt-1 w-full rounded-xl border px-3 py-2"
                value={p.brand || "XPrinter"}
                onChange={(e) => updateRow(idx, "brand", e.target.value)}
              >
                {BRANDS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-semibold">{t("printing.windowsPrinter")}</span>
              <input
                className="mt-1 w-full rounded-xl border px-3 py-2"
                placeholder="XPrinter XP-350B"
                value={p.windows_printer_name || ""}
                onChange={(e) => updateRow(idx, "windows_printer_name", e.target.value)}
              />
            </label>
            {p.connection_type === "network" ? (
              <>
                <label className="block text-sm">
                  <span className="font-semibold">IP</span>
                  <input
                    className="mt-1 w-full rounded-xl border px-3 py-2"
                    value={p.ip_address || ""}
                    onChange={(e) => updateRow(idx, "ip_address", e.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  <span className="font-semibold">{t("traceability.printerPort")}</span>
                  <input
                    type="number"
                    className="mt-1 w-full rounded-xl border px-3 py-2"
                    value={p.port ?? 9100}
                    onChange={(e) => updateRow(idx, "port", e.target.value)}
                  />
                </label>
              </>
            ) : null}
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={Boolean(p.auto_print_enabled)}
              onChange={(e) => updateRow(idx, "auto_print_enabled", e.target.checked)}
            />
            {t("traceability.autoPrint")}
          </label>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setPrinters((rows) => [...rows, emptyPrinter()])}
          className="rounded-2xl border px-4 py-2 text-sm font-semibold"
        >
          + {t("traceability.addPrinter")}
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={save}
          className="rounded-2xl bg-black px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? t("common.saving") : t("common.save")}
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
