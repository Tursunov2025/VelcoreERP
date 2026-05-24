import { useEffect, useState } from "react";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useAuth } from "../context/AuthContext";

export default function WarehousePage() {
  const { isAdmin, isOmbor } = useAuth();
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await api.getReadyWarehouse(search));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    load();
  };

  if (!isAdmin && !isOmbor) {
    return (
      <p className="text-center text-red-500 py-12">
        Faqat Ombor operatori yoki admin ko&apos;ra oladi
      </p>
    );
  }

  if (loading && !items.length) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title="Ombor"
        subtitle="Tayyor mahsulotlar — yuk chiqarishga tayyor"
      />

      <form onSubmit={handleSearch} className="mb-6">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Qidirish: mijoz, manzil, ID..."
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black md:max-w-md"
        />
      </form>

      <ErrorAlert message={error} onRetry={load} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <Card key={item.id} className="transition hover:shadow-xl">
            <p className="text-xs text-gray-400">Zakaz #{item.order_id}</p>
            <h3 className="text-lg font-bold">{item.client}</h3>
            <p className="text-sm text-gray-500">{item.phone}</p>
            <p className="mt-2 font-black text-green-600">
              {Number(item.amount).toLocaleString()} so&apos;m
            </p>
            {item.destination && (
              <p className="mt-2 text-sm">📍 {item.destination}</p>
            )}
            <p className="mt-2 text-xs text-gray-400">
              Omborga: {item.stored_at ? new Date(item.stored_at).toLocaleString() : "—"}
            </p>
            <p className="text-xs">Miqdor: {item.quantity}</p>
          </Card>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <p className="py-12 text-center text-gray-500">Omborda mahsulot yo&apos;q</p>
      )}
    </div>
  );
}
