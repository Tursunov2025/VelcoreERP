import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function FinancePage() {
  const { isAdmin } = useAuth();
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expense, setExpense] = useState({ title: "", amount: "", category: "general" });
  const [income, setIncome] = useState({ title: "", amount: "", source: "manual" });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [s, r] = await Promise.all([
        api.getFinanceSummary(),
        api.getFinanceRecords(),
      ]);
      setSummary(s);
      setRecords(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader title="Moliya" subtitle="Daromad, xarajat va sof foyda" />
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-gray-500">Daromad</p>
          <p className="text-2xl font-black text-green-600">
            {Number(summary?.total_income || 0).toLocaleString()} so&apos;m
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Xarajat</p>
          <p className="text-2xl font-black text-red-600">
            {Number(summary?.total_expenses || 0).toLocaleString()} so&apos;m
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Sof foyda</p>
          <p className="text-2xl font-black text-blue-600">
            {Number(summary?.net_profit || 0).toLocaleString()} so&apos;m
          </p>
        </Card>
      </div>

      {isAdmin && (
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          <Card>
            <h2 className="mb-4 font-bold">Xarajat qo&apos;shish</h2>
            <div className="space-y-3">
              <input
                placeholder="Sarlavha"
                value={expense.title}
                onChange={(e) => setExpense({ ...expense, title: e.target.value })}
                className="w-full rounded-2xl border px-4 py-3"
              />
              <input
                type="number"
                placeholder="Summa"
                value={expense.amount}
                onChange={(e) => setExpense({ ...expense, amount: e.target.value })}
                className="w-full rounded-2xl border px-4 py-3"
              />
              <button
                type="button"
                onClick={async () => {
                  await api.addExpense({
                    ...expense,
                    amount: Number(expense.amount),
                  });
                  setExpense({ title: "", amount: "", category: "general" });
                  load();
                }}
                className="w-full rounded-2xl bg-red-500 py-3 text-white"
              >
                Saqlash
              </button>
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 font-bold">Daromad qo&apos;shish</h2>
            <div className="space-y-3">
              <input
                placeholder="Sarlavha"
                value={income.title}
                onChange={(e) => setIncome({ ...income, title: e.target.value })}
                className="w-full rounded-2xl border px-4 py-3"
              />
              <input
                type="number"
                placeholder="Summa"
                value={income.amount}
                onChange={(e) => setIncome({ ...income, amount: e.target.value })}
                className="w-full rounded-2xl border px-4 py-3"
              />
              <button
                type="button"
                onClick={async () => {
                  await api.addIncome({
                    ...income,
                    amount: Number(income.amount),
                  });
                  setIncome({ title: "", amount: "", source: "manual" });
                  load();
                }}
                className="w-full rounded-2xl bg-green-600 py-3 text-white"
              >
                Saqlash
              </button>
            </div>
          </Card>
        </div>
      )}

      <Card>
        <h2 className="mb-4 font-bold">Moliya tarixi</h2>
        <div className="max-h-96 space-y-2 overflow-y-auto">
          {records.map((r) => (
            <div
              key={`${r.type}-${r.id}`}
              className="flex justify-between rounded-xl border p-3"
            >
              <div>
                <p className="font-bold">{r.title}</p>
                <p className="text-xs text-gray-500">{r.category}</p>
              </div>
              <p
                className={`font-black ${
                  r.type === "income" ? "text-green-600" : "text-red-600"
                }`}
              >
                {r.type === "income" ? "+" : "-"}
                {Number(r.amount).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
