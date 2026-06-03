import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { jsPDF } from "jspdf";
import { api, getStoredTokens, API_BASE } from "../api/client";
import StageTimeline from "../components/controlCenter/StageTimeline";
import AdminRoute from "../components/layout/AdminRoute";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useLocale } from "../context/LocaleContext";

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function OrdersControlCenterPage() {
  const { t } = useLocale();
  const [data, setData] = useState({ items: [], summary: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [customer, setCustomer] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("all");
  const [delayedOnly, setDelayedOnly] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await api.controlCenterOrders({
        q,
        customer,
        status,
        type,
        delayed_only: delayedOnly,
      });
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [q, customer, status, type, delayedOnly]);

  useEffect(() => {
    setLoading(true);
    const timer = window.setTimeout(load, 350);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const id = setInterval(load, 25000);
    return () => clearInterval(id);
  }, [load]);

  const exportCsv = async () => {
    const tokens = getStoredTokens();
    const params = new URLSearchParams({
      q,
      customer,
      status,
      type,
      delayed_only: delayedOnly ? "true" : "false",
    });
    const res = await fetch(`${API_BASE}/control-center/orders/export.csv?${params}`, {
      headers: tokens?.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {},
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    downloadBlob(blob, "orders-control-center.csv");
  };

  const exportPdf = () => {
    const doc = new jsPDF({ orientation: "landscape" });
    doc.setFontSize(14);
    doc.text(t("controlCenter.ordersTitle"), 14, 16);
    doc.setFontSize(9);
    let y = 26;
    data.items.slice(0, 40).forEach((row) => {
      const line = `${row.reference} | ${row.customer} | ${row.status} | ${row.current_stage} | ${row.progress_pct}%`;
      doc.text(line.substring(0, 120), 14, y);
      y += 6;
      if (y > 190) {
        doc.addPage();
        y = 16;
      }
    });
    doc.save("orders-control-center.pdf");
  };

  const summary = data.summary || {};

  return (
    <AdminRoute>
      <div className="pb-24">
        <PageHeader
          title={t("controlCenter.ordersTitle")}
          subtitle={t("controlCenter.ordersSubtitle")}
        />

        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
            <p className="text-2xl font-black">{summary.total ?? 0}</p>
            <p className="text-xs text-[var(--brand-muted)]">{t("controlCenter.totalItems")}</p>
          </div>
          <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
            <p className="text-2xl font-black text-red-600">{summary.delayed ?? 0}</p>
            <p className="text-xs text-[var(--brand-muted)]">{t("controlCenter.delayed")}</p>
          </div>
          <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
            <p className="text-2xl font-black">{summary.orders ?? 0}</p>
            <p className="text-xs text-[var(--brand-muted)]">{t("controlCenter.legacyOrders")}</p>
          </div>
          <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
            <p className="text-2xl font-black">{summary.mes_jobs ?? 0}</p>
            <p className="text-xs text-[var(--brand-muted)]">{t("controlCenter.mesJobs")}</p>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("controlCenter.search")}
            className="min-h-[48px] min-w-[140px] flex-1 rounded-xl border px-3"
          />
          <input
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            placeholder={t("controlCenter.customerFilter")}
            className="min-h-[48px] min-w-[140px] flex-1 rounded-xl border px-3"
          />
          <input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            placeholder={t("controlCenter.statusFilter")}
            className="min-h-[48px] w-32 rounded-xl border px-3"
          />
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="min-h-[48px] rounded-xl border px-3"
          >
            <option value="all">{t("controlCenter.typeAll")}</option>
            <option value="order">{t("controlCenter.typeOrders")}</option>
            <option value="mes_job">{t("controlCenter.typeJobs")}</option>
          </select>
          <label className="flex min-h-[48px] items-center gap-2 rounded-xl border bg-white px-3 text-sm">
            <input
              type="checkbox"
              checked={delayedOnly}
              onChange={(e) => setDelayedOnly(e.target.checked)}
            />
            {t("controlCenter.delayedOnly")}
          </label>
          <button
            type="button"
            onClick={exportCsv}
            className="min-h-[48px] rounded-xl border bg-white px-4 font-semibold"
          >
            Excel (CSV)
          </button>
          <button
            type="button"
            onClick={exportPdf}
            className="min-h-[48px] rounded-xl border bg-white px-4 font-semibold"
          >
            PDF
          </button>
        </div>

        <ErrorAlert message={error} onRetry={load} />
        {loading ? <LoadingSpinner /> : null}

        <div className="space-y-3">
          {data.items?.map((item) => (
            <article
              key={`${item.type}-${item.id}`}
              className={`rounded-2xl border bg-[var(--brand-card)] p-4 ${
                item.is_delayed ? "border-red-400 ring-1 ring-red-200" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-mono text-xs text-gray-500">{item.reference}</p>
                  <h3 className="text-lg font-bold">{item.customer || item.title}</h3>
                  <p className="text-sm text-[var(--brand-muted)]">
                    {item.type === "mes_job" ? "MES" : t("controlCenter.legacyOrders")} · {item.status}
                    {item.priority ? ` · ${item.priority}` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-black">{Math.round(item.progress_pct || 0)}%</p>
                  {item.is_delayed ? (
                    <span className="text-xs font-bold text-red-600">{t("controlCenter.delayed")}</span>
                  ) : null}
                  <Link
                    to={item.link}
                    className="mt-1 block text-sm text-[var(--brand-primary)] hover:underline"
                  >
                    {t("controlCenter.open")}
                  </Link>
                </div>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, item.progress_pct || 0)}%`,
                    backgroundColor: item.is_delayed ? "#dc2626" : "var(--brand-primary)",
                  }}
                />
              </div>
              <p className="mt-2 text-xs font-semibold text-gray-600">
                {t("controlCenter.currentStage")}: {item.current_stage}
              </p>
              <StageTimeline timeline={item.timeline} />
            </article>
          ))}
          {!loading && !data.items?.length ? (
            <p className="py-12 text-center text-[var(--brand-muted)]">{t("controlCenter.empty")}</p>
          ) : null}
        </div>
      </div>
    </AdminRoute>
  );
}
