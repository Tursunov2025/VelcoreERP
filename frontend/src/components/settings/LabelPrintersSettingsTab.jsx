import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

const BRANDS = ["Zebra", "TSC", "XPrinter", "Godex", "Generic"];

const emptyPrinter = () => ({
  name: "",
  brand: "Zebra",
  ip_address: "",
  port: 9100,
  auto_print_enabled: false,
});

export default function LabelPrintersSettingsTab() {
  const { t } = useLocale();
  const [printers, setPrinters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  const load = () => {
    setLoading(true);
    api
      .adminGetLabelPrinters()
      .then((data) => setPrinters(data?.printers?.length ? data.printers : [emptyPrinter()]))
      .catch((e) => setToast(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
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
        brand: p.brand || "Zebra",
        ip_address: (p.ip_address || "").trim(),
        port: Number(p.port) || 9100,
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

  if (loading) {
    return <p className="text-sm text-[var(--brand-muted)]">{t("common.loading")}</p>;
  }

  return (
    <div className="space-y-4">
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
              <span className="font-semibold">{t("traceability.printerBrand")}</span>
              <select
                className="mt-1 w-full rounded-xl border px-3 py-2"
                value={p.brand || "Zebra"}
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
