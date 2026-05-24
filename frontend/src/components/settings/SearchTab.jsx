import { useState } from "react";
import { api } from "../../api/client";
import { DEPARTMENTS, PRODUCTION_STAGES } from "../../constants/workflow";
import Toast from "../ui/Toast";

export default function SearchTab() {
  const [filters, setFilters] = useState({
    client: "",
    operator: "",
    stage: "",
    department: "",
    status: "",
    date_from: "",
    date_to: "",
    include_deleted: false,
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");

  const search = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setLoading(true);
    try {
      const data = await api.adminSearchOrders(filters);
      setResults(data);
      setToast(`${data.length} ta topildi`);
    } catch (err) {
      setToast(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">Kengaytirilgan qidiruv</h2>
      <form onSubmit={search} className="mb-6 grid gap-3 sm:grid-cols-2">
        <input
          placeholder="Mijoz"
          value={filters.client}
          onChange={(e) => setFilters({ ...filters, client: e.target.value })}
          className="rounded-xl border px-4 py-3"
        />
        <input
          placeholder="Operator"
          value={filters.operator}
          onChange={(e) => setFilters({ ...filters, operator: e.target.value })}
          className="rounded-xl border px-4 py-3"
        />
        <select
          value={filters.stage}
          onChange={(e) => setFilters({ ...filters, stage: e.target.value })}
          className="rounded-xl border px-4 py-3"
        >
          <option value="">Bosqich</option>
          {PRODUCTION_STAGES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={filters.department}
          onChange={(e) => setFilters({ ...filters, department: e.target.value })}
          className="rounded-xl border px-4 py-3"
        >
          <option value="">Bo&apos;lim</option>
          {DEPARTMENTS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={filters.date_from}
          onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
          className="rounded-xl border px-4 py-3"
        />
        <input
          type="date"
          value={filters.date_to}
          onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
          className="rounded-xl border px-4 py-3"
        />
        <label className="flex items-center gap-2 sm:col-span-2">
          <input
            type="checkbox"
            checked={filters.include_deleted}
            onChange={(e) =>
              setFilters({ ...filters, include_deleted: e.target.checked })
            }
          />
          O&apos;chirilganlarni ham qidirish
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-black py-3 font-bold text-white sm:col-span-2"
        >
          {loading ? "Qidirilmoqda..." : "Qidirish"}
        </button>
      </form>

      <div className="space-y-2">
        {results.map((o) => (
          <div key={o.id} className="rounded-xl border bg-white p-3 text-sm">
            <span className="font-bold">#{o.id}</span> {o.client} — {o.status}
            {o.deleted_at && <span className="text-red-500"> (deleted)</span>}
          </div>
        ))}
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
