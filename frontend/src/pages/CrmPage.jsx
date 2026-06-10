import { useEffect, useState } from "react";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";

const CURRENCIES = ["UZS", "KZT", "USD", "RUB"];

function money(value) {
  return Number(value || 0).toLocaleString();
}

export default function CrmPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canPay = isAdmin || hasPermission("finance");

  const [ledger, setLedger] = useState([]);
  const [payments, setPayments] = useState([]);
  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [payForm, setPayForm] = useState({ customer: "", amount: "", currency: "UZS", notes: "" });

  const load = async () => {
    setError("");
    try {
      const [ledgerData, paymentData] = await Promise.all([
        api.crmLedger(search),
        api.crmPayments(selected).catch(() => ({ payments: [] })),
      ]);
      setLedger(ledgerData.ledger || []);
      setPayments(paymentData.payments || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = window.setTimeout(load, 250);
    return () => window.clearTimeout(id);
  }, [search, selected]);

  const recordPayment = async (e) => {
    e.preventDefault();
    if (!payForm.customer.trim() || !Number(payForm.amount)) return;
    try {
      await api.crmRecordPayment({
        customer: payForm.customer.trim(),
        amount: Number(payForm.amount),
        currency: payForm.currency,
        notes: payForm.notes,
      });
      setToast("Payment recorded");
      setPayForm({ customer: "", amount: "", currency: "UZS", notes: "" });
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const totals = ledger.reduce(
    (acc, row) => ({
      orders: acc.orders + row.total_orders,
      paid: acc.paid + row.paid_amount,
      debt: acc.debt + row.outstanding_debt,
    }),
    { orders: 0, paid: 0, debt: 0 }
  );

  return (
    <div className="pb-24">
      <BackButton fallback="/" label="Dashboard" className="mb-4" />
      <PageHeader title="CRM — Customer Ledger" subtitle="Orders, payments and outstanding debt (UZS)" />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Total Orders</p>
          <p className="mt-1 text-2xl font-black">{money(totals.orders)}</p>
        </div>
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Paid Amount</p>
          <p className="mt-1 text-2xl font-black text-green-600">{money(totals.paid)}</p>
        </div>
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Outstanding Debt</p>
          <p className="mt-1 text-2xl font-black text-red-500">{money(totals.debt)}</p>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search customer..."
          className="flex-1 rounded-xl border bg-[var(--brand-card)] px-4 py-3 text-[var(--brand-text)]"
        />
      </div>

      {canPay ? (
        <form
          onSubmit={recordPayment}
          className="mb-6 grid gap-2 rounded-3xl border bg-[var(--brand-card)] p-4 sm:grid-cols-5"
        >
          <input
            value={payForm.customer}
            onChange={(e) => setPayForm({ ...payForm, customer: e.target.value })}
            placeholder="Customer"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <input
            type="number"
            min="0"
            step="any"
            value={payForm.amount}
            onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })}
            placeholder="Amount"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <select
            value={payForm.currency}
            onChange={(e) => setPayForm({ ...payForm, currency: e.target.value })}
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            value={payForm.notes}
            onChange={(e) => setPayForm({ ...payForm, notes: e.target.value })}
            placeholder="Notes"
            className="rounded-xl border bg-transparent px-3 py-2.5 text-sm"
          />
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            + Record Payment
          </button>
        </form>
      ) : null}

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-2">
        {ledger.map((row) => (
          <div
            key={row.customer}
            className={`rounded-2xl border bg-[var(--brand-card)] p-4 ${
              selected === row.customer ? "ring-2 ring-[var(--brand-button)]" : ""
            }`}
          >
            <button
              type="button"
              onClick={() => setSelected(selected === row.customer ? "" : row.customer)}
              className="flex w-full flex-wrap items-center justify-between gap-2 text-left"
            >
              <div>
                <p className="font-bold text-[var(--brand-text)]">{row.customer}</p>
                <p className="text-xs text-[var(--brand-muted)]">{row.orders_count} orders</p>
              </div>
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <span>
                  <span className="text-xs text-[var(--brand-muted)]">Orders </span>
                  <span className="font-bold">{money(row.total_orders)}</span>
                </span>
                <span>
                  <span className="text-xs text-[var(--brand-muted)]">Paid </span>
                  <span className="font-bold text-green-600">{money(row.paid_amount)}</span>
                </span>
                <span>
                  <span className="text-xs text-[var(--brand-muted)]">Debt </span>
                  <span
                    className={`font-bold ${
                      row.outstanding_debt > 0 ? "text-red-500" : "text-green-600"
                    }`}
                  >
                    {money(row.outstanding_debt)}
                  </span>
                </span>
              </div>
            </button>
            {selected === row.customer ? (
              <div className="mt-3 border-t pt-3">
                <p className="mb-2 text-xs font-bold uppercase text-[var(--brand-muted)]">
                  Payments
                </p>
                {payments.length === 0 ? (
                  <p className="text-sm text-[var(--brand-muted)]">No payments recorded</p>
                ) : (
                  <div className="space-y-1">
                    {payments.map((p) => (
                      <div key={p.id} className="flex items-center justify-between text-sm">
                        <span className="text-[var(--brand-muted)]">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"} ·{" "}
                          {p.created_by}
                          {p.notes ? ` · ${p.notes}` : ""}
                        </span>
                        <span className="font-bold text-green-600">
                          +{money(p.amount)} {p.currency}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        ))}
        {!loading && ledger.length === 0 ? (
          <p className="py-12 text-center text-sm text-[var(--brand-muted)]">No customers found</p>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
