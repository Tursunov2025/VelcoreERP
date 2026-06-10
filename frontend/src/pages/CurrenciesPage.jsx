import { useEffect, useState } from "react";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const CODES = ["UZS", "KZT", "USD", "RUB"];

export default function CurrenciesPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("finance");

  const [currencies, setCurrencies] = useState([]);
  const [historyCode, setHistoryCode] = useState("USD");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [rateForm, setRateForm] = useState({ currency_code: "USD", rate_to_base: "" });
  const [converter, setConverter] = useState({ amount: "100", from: "USD", to: "UZS" });
  const [converted, setConverted] = useState(null);

  const load = async () => {
    setError("");
    try {
      const [list, hist] = await Promise.all([
        api.currencies(),
        api.currencyRateHistory(historyCode).catch(() => ({ history: [] })),
      ]);
      setCurrencies(list.currencies || []);
      setHistory(hist.history || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [historyCode]);

  const addRate = async (e) => {
    e.preventDefault();
    if (!Number(rateForm.rate_to_base)) return;
    try {
      await api.addCurrencyRate({
        currency_code: rateForm.currency_code,
        rate_to_base: Number(rateForm.rate_to_base),
      });
      setToast(`Rate saved: 1 ${rateForm.currency_code} = ${rateForm.rate_to_base} UZS`);
      setRateForm({ ...rateForm, rate_to_base: "" });
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const convert = async (e) => {
    e.preventDefault();
    setConverted(null);
    try {
      const res = await api.convertCurrency(
        Number(converter.amount) || 0,
        converter.from,
        converter.to
      );
      setConverted(res);
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div className="pb-24">
      <BackButton fallback="/" label="Dashboard" className="mb-4" />
      <PageHeader title="Currencies" subtitle="Exchange rates, history and conversion (base: UZS)" />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {/* Currency table */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {currencies.map((currency) => (
          <div key={currency.code} className="rounded-3xl border bg-[var(--brand-card)] p-4">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xl font-black text-[var(--brand-text)]">
                {currency.code}
              </p>
              <span className="text-lg">{currency.symbol}</span>
            </div>
            <p className="text-xs text-[var(--brand-muted)]">{currency.name}</p>
            <p className="mt-2 text-lg font-bold text-[var(--brand-text)]">
              {currency.is_base
                ? "Base"
                : currency.rate_to_base != null
                  ? `${currency.rate_to_base.toLocaleString()} UZS`
                  : "No rate"}
            </p>
            {currency.rate_date ? (
              <p className="text-xs text-[var(--brand-muted)]">
                {new Date(currency.rate_date).toLocaleDateString()}
              </p>
            ) : null}
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Rate management + history */}
        <div className="rounded-3xl border bg-[var(--brand-card)] p-5">
          <h2 className="mb-3 font-bold text-[var(--brand-text)]">📈 Exchange Rate History</h2>
          {canManage ? (
            <form onSubmit={addRate} className="mb-4 flex flex-wrap gap-2">
              <select
                value={rateForm.currency_code}
                onChange={(e) => setRateForm({ ...rateForm, currency_code: e.target.value })}
                className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
              >
                {CODES.filter((c) => c !== "UZS").map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                step="any"
                value={rateForm.rate_to_base}
                onChange={(e) => setRateForm({ ...rateForm, rate_to_base: e.target.value })}
                placeholder="Rate in UZS"
                className="w-36 rounded-xl border bg-transparent px-3 py-2.5 text-sm"
              />
              <button
                type="submit"
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                + Add Rate
              </button>
            </form>
          ) : null}
          <div className="mb-3 flex gap-1">
            {CODES.filter((c) => c !== "UZS").map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setHistoryCode(code)}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold ${
                  historyCode === code
                    ? "text-white"
                    : "border text-[var(--brand-muted)]"
                }`}
                style={historyCode === code ? { backgroundColor: "var(--brand-button)" } : undefined}
              >
                {code}
              </button>
            ))}
          </div>
          {history.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--brand-muted)]">
              No rates recorded for {historyCode}
            </p>
          ) : (
            <div className="max-h-72 space-y-1 overflow-y-auto">
              {history.map((row) => (
                <div
                  key={row.id}
                  className="flex items-center justify-between rounded-xl border px-3 py-2 text-sm"
                >
                  <span className="text-[var(--brand-muted)]">
                    {row.rate_date ? new Date(row.rate_date).toLocaleString() : "—"} ·{" "}
                    {row.created_by}
                  </span>
                  <span className="font-mono font-bold text-[var(--brand-text)]">
                    {row.rate_to_base.toLocaleString()} UZS
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Converter */}
        <div className="rounded-3xl border bg-[var(--brand-card)] p-5">
          <h2 className="mb-3 font-bold text-[var(--brand-text)]">🔁 Currency Converter</h2>
          <form onSubmit={convert} className="space-y-3">
            <input
              type="number"
              min="0"
              step="any"
              value={converter.amount}
              onChange={(e) => setConverter({ ...converter, amount: e.target.value })}
              placeholder="Amount"
              className="w-full rounded-xl border bg-transparent px-4 py-3 text-lg font-bold"
            />
            <div className="flex items-center gap-2">
              <select
                value={converter.from}
                onChange={(e) => setConverter({ ...converter, from: e.target.value })}
                className="flex-1 rounded-xl border bg-transparent px-3 py-2.5"
              >
                {CODES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() =>
                  setConverter({ ...converter, from: converter.to, to: converter.from })
                }
                className="rounded-xl border px-3 py-2.5"
                aria-label="Swap currencies"
              >
                ⇄
              </button>
              <select
                value={converter.to}
                onChange={(e) => setConverter({ ...converter, to: e.target.value })}
                className="flex-1 rounded-xl border bg-transparent px-3 py-2.5"
              >
                {CODES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="w-full rounded-xl px-4 py-3 font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              Convert
            </button>
          </form>
          {converted ? (
            <div className="mt-4 rounded-2xl border bg-[var(--brand-background)] p-4 text-center">
              <p className="text-sm text-[var(--brand-muted)]">
                {converted.amount.toLocaleString()} {converted.from} =
              </p>
              <p className="text-3xl font-black text-[var(--brand-text)]">
                {converted.converted.toLocaleString()} {converted.to}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
