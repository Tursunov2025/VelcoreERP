import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";

export default function SvarshikStockPage({ mode = "svarshik" }) {
  const { isAdmin, department, hasPermission } = useAuth();
  const { t, formatDateTime, formatNumber } = useLocale();
  const isLazer = mode === "lazer";
  const canUse = isLazer
    ? isAdmin || hasPermission("mes_terminal_lazer")
    : isAdmin || department === "Ombor" || department === "Svarka";
  const canWrite = !isLazer && (isAdmin || department === "Ombor");
  const [items, setItems] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("stock");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canUse) return;
    try {
      const [stock, transactions] = await Promise.all([
        api.warehouseDetailStock({ q }),
        isLazer
          ? api.warehouseDetailTransactions({ operation: "IN" })
          : canWrite
            ? api.warehouseDetailTransactions()
            : Promise.resolve([]),
      ]);
      setItems(stock);
      setHistory(transactions);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, [canUse, canWrite, isLazer, q]);

  useEffect(() => {
    load();
  }, [load]);

  const action = async (item, operation) => {
    const quantity = window.prompt(t("stock.quantityPrompt"));
    if (!quantity) return;
    try {
      await api.warehouseDetailStockAction(operation, {
        stock_id: item.id,
        quantity,
        reason: operation === "adjustment" ? window.prompt(t("stock.reasonPrompt")) || "Manual" : "",
      });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  if (!canUse) {
    return <p className="py-12 text-center text-red-500">{t("errors.accessDenied")}</p>;
  }

  return (
    <div>
      <PageHeader
        title={isLazer ? t("stock.lazerTitle") : t("stock.svarkaTitle")}
        subtitle={t("stock.reusableDetails")}
      />
      <div className="mb-4 flex gap-2">
        <button type="button" onClick={() => setTab("stock")} className="rounded-xl border px-4 py-2">{t("stock.balance")}</button>
        {(isLazer || canWrite) && <button type="button" onClick={() => setTab("history")} className="rounded-xl border px-4 py-2">{t("stock.history")}</button>}
      </div>
      {error ? <p className="mb-3 text-red-500">{error}</p> : null}
      {tab === "stock" ? (
        <>
          <input value={q} onChange={(event) => setQ(event.target.value)} placeholder={t("stock.searchDetails")} className="mb-4 w-full rounded-xl border bg-[var(--brand-card)] px-4 py-3" />
          <div className="overflow-x-auto rounded-2xl border bg-[var(--brand-card)]">
            <table className="min-w-[1200px] w-full text-sm">
              <thead><tr className="border-b text-left">{["code", "detail", "dimensions", "material", "balance", "reserved", "available", "unit", "status", "updated", ...(canWrite ? ["actions"] : [])].map((key) => <th className="p-3" key={key}>{t(`stock.${key}`)}</th>)}</tr></thead>
              <tbody>{items.map((item) => <tr className="border-b" key={item.id}>
                <td className="p-3 font-mono">{item.detail_code}</td><td className="p-3">{item.detail_name}</td><td className="p-3">{item.dimensions || "—"}</td><td className="p-3">{item.material || "—"}</td>
                <td className="p-3 font-bold">{formatNumber(item.quantity)}</td><td className="p-3 font-bold">{formatNumber(item.reserved_quantity)}</td><td className="p-3 font-bold">{formatNumber(item.available_quantity)}</td><td className="p-3">{item.unit}</td>
                <td className={`p-3 font-bold ${item.available_quantity > 0 ? "text-green-600" : "text-red-500"}`}>{localizedCanonical(t, "statuses", item.status)}</td><td className="p-3">{item.updated_at && formatDateTime(item.updated_at)}</td>
                {canWrite && <td className="p-3"><div className="flex gap-2"><button onClick={() => action(item, "out")}>{t("stock.out")}</button><button onClick={() => action(item, "reserve")}>{t("stock.reserve")}</button><button onClick={() => action(item, "release")}>{t("stock.release")}</button><button onClick={() => action(item, "adjustment")}>{t("stock.adjustment")}</button></div></td>}
              </tr>)}</tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-[var(--brand-card)]"><table className="min-w-[900px] w-full text-sm">
          <thead><tr className="border-b text-left">{["date", "detail", "operation", "quantity", "before", "after", "job", "operator", "reason"].map((key) => <th className="p-3" key={key}>{t(`stock.${key}`)}</th>)}</tr></thead>
          <tbody>{history.map((row) => <tr className="border-b" key={row.id}><td className="p-3">{row.created_at && formatDateTime(row.created_at)}</td><td className="p-3">#{row.detail_id}</td><td className="p-3">{localizedCanonical(t, "statuses", row.operation)}</td><td className="p-3">{formatNumber(row.quantity)}</td><td className="p-3">{formatNumber(row.quantity_before)}</td><td className="p-3">{formatNumber(row.quantity_after)}</td><td className="p-3">{row.order_id || "—"}</td><td className="p-3">{row.operator}</td><td className="p-3">{row.reason}</td></tr>)}</tbody>
        </table></div>
      )}
    </div>
  );
}
