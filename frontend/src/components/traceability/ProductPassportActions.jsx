import { Link } from "react-router-dom";
import { useState } from "react";
import { api, authenticatedFetch } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

async function downloadResponse(response, filename) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function ProductPassportActions({ packageId, serials = [], compact = false, onMessage }) {
  const { t } = useLocale();
  const [batchBusy, setBatchBusy] = useState(false);
  const [activeSerials, setActiveSerials] = useState(serials);
  const first = activeSerials[0];
  const report = (message) => onMessage?.(message);
  const generate = async () => {
    try {
      const result = await api.generateProductPassports(Number(packageId));
      setActiveSerials((result.items || []).map((item) => item.serial_number));
      report(t("traceability.generationReady").replace("{count}", String(result.items?.length || 0)));
    } catch (error) {
      report(error?.code === "traceability_generate_required" ? t("traceability.errorGenerateRequired") : t("traceability.error"));
    }
  };
  const batchPrint = async () => {
    if (!activeSerials.length) return;
    setBatchBusy(true);
    try {
      const response = await authenticatedFetch(api.traceabilityBatchLabelPdfUrl(), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ serial_numbers: activeSerials, size: "60x60" }) });
      await downloadResponse(response, "product-passports-60x60.pdf");
    } catch (error) { report(t("traceability.error")); }
    finally { setBatchBusy(false); }
  };
  const print = async (serial) => {
    try {
      await downloadResponse(
        await authenticatedFetch(api.productPassportLabelUrl(serial, "60x60")),
        `${serial}-60x60.png`,
      );
    } catch (error) {
      report(error?.message || t("traceability.error"));
    }
  };
  if (!first && !packageId) return null;
  return (
    <div className={`flex flex-wrap items-center gap-2 ${compact ? "text-xs" : "text-sm"}`}>
      {first ? <Link className="text-blue-600 hover:underline" to={`/traceability/products/${encodeURIComponent(first)}`}>{t("traceability.openPassport")}</Link> : null}
      {packageId ? <button type="button" className="rounded-lg border px-2 py-1" onClick={generate}>{t("traceability.generateQr")}</button> : null}
      {first ? <button type="button" className="rounded-lg border px-2 py-1" onClick={() => print(first)}>{t("traceability.printLabel")}</button> : null}
      {activeSerials.length > 1 ? <button type="button" className="rounded-lg border px-2 py-1" disabled={batchBusy} onClick={batchPrint}>{batchBusy ? t("common.saving") : t("traceability.batchPrintLabels")}</button> : null}
    </div>
  );
}
