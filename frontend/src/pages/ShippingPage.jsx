import { useEffect, useState } from "react";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useAuth } from "../context/AuthContext";

export default function ShippingPage() {
  const { isAdmin, isOmbor } = useAuth();
  const [items, setItems] = useState([]);
  const [archive, setArchive] = useState([]);
  const [selected, setSelected] = useState([]);
  const [destination, setDestination] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("dispatch");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [ready, arch] = await Promise.all([
        api.getReadyWarehouse(),
        api.getShippingArchive(),
      ]);
      setItems(ready);
      setArchive(arch);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = (id) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const dispatch = async () => {
    if (!selected.length) {
      setError("Mahsulot tanlang");
      return;
    }
    setLoading(true);
    try {
      await api.dispatchShipment({
        warehouse_item_ids: selected,
        destination,
        comment,
      });
      setSelected([]);
      setDestination("");
      setComment("");
      await load();
      setTab("archive");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!isAdmin && !isOmbor) {
    return <p className="text-center text-red-500 py-12">Ruxsat yo&apos;q</p>;
  }

  if (loading && !items.length) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader title="Yuk chiqarish" subtitle="Tayyor mahsulotlarni jo'natish" />

      <div className="mb-6 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("dispatch")}
          className={`rounded-2xl px-5 py-2 text-sm font-bold ${
            tab === "dispatch" ? "bg-black text-white" : "bg-gray-200"
          }`}
        >
          Yuk chiqarish
        </button>
        <button
          type="button"
          onClick={() => setTab("archive")}
          className={`rounded-2xl px-5 py-2 text-sm font-bold ${
            tab === "archive" ? "bg-black text-white" : "bg-gray-200"
          }`}
        >
          Arxiv
        </button>
      </div>

      <ErrorAlert message={error} onRetry={load} />

      {tab === "dispatch" ? (
        <>
          <Card className="mb-6">
            <h2 className="mb-4 font-bold">Tanlangan: {selected.length}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                placeholder="Manzil / destination"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="rounded-2xl border px-4 py-3"
              />
              <input
                placeholder="Izoh"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="rounded-2xl border px-4 py-3"
              />
            </div>
            <button
              type="button"
              onClick={dispatch}
              disabled={loading || !selected.length}
              className="mt-4 w-full rounded-2xl bg-green-600 py-4 font-bold text-white disabled:opacity-50 sm:w-auto sm:px-10"
            >
              Yuk chiqarildi
            </button>
          </Card>

          <div className="space-y-3">
            {items.map((item) => (
              <label
                key={item.id}
                className={`flex cursor-pointer items-center gap-4 rounded-2xl border p-4 transition ${
                  selected.includes(item.id) ? "border-black bg-gray-50" : ""
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  onChange={() => toggle(item.id)}
                  className="h-5 w-5"
                />
                <div className="flex-1">
                  <p className="font-bold">
                    #{item.order_id} — {item.client}
                  </p>
                  <p className="text-sm text-gray-500">{item.destination}</p>
                </div>
                <p className="font-black text-green-600">
                  {Number(item.amount).toLocaleString()}
                </p>
              </label>
            ))}
          </div>
        </>
      ) : (
        <div className="space-y-3">
          {archive.map((row) => (
            <Card key={row.id}>
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-bold">{row.client}</p>
                  <p className="text-sm text-gray-500">{row.destination}</p>
                  <p className="text-xs text-gray-400">
                    {row.operator_username} —{" "}
                    {row.shipped_at
                      ? new Date(row.shipped_at).toLocaleString()
                      : ""}
                  </p>
                </div>
                <p className="font-black">{Number(row.amount).toLocaleString()} so&apos;m</p>
              </div>
              {row.comment && (
                <p className="mt-2 text-sm italic text-gray-500">{row.comment}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
