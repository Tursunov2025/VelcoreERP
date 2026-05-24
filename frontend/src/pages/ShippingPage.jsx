import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useAuth } from "../context/AuthContext";
import {
  downloadShipmentPdf,
  printShipmentPdf,
} from "../utils/shipmentGroupPdf";

export default function ShippingPage() {
  const { isAdmin, isOmbor } = useAuth();
  const [items, setItems] = useState([]);
  const [groups, setGroups] = useState([]);
  const [selected, setSelected] = useState([]);
  const [destination, setDestination] = useState("");
  const [comment, setComment] = useState("");
  const [responsible, setResponsible] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("dispatch");
  const [filters, setFilters] = useState({
    q: "",
    operator: "",
    destination: "",
    shipment_id: "",
    date_from: "",
    date_to: "",
    product: "",
  });
  const [expandedId, setExpandedId] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const [ready, arch] = await Promise.all([
        api.getReadyWarehouse(),
        api.getShipmentGroups(filters),
      ]);
      setItems(ready);
      setGroups(arch);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const toggle = (id) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selected.length === items.length) {
      setSelected([]);
    } else {
      setSelected(items.map((i) => i.id));
    }
  };

  const dispatch = async () => {
    if (!selected.length) {
      setError("Mahsulot tanlang");
      return;
    }
    setLoading(true);
    try {
      const res = await api.dispatchShipment({
        warehouse_item_ids: selected,
        destination,
        comment: comment || "Yuk chiqarildi",
        responsible_operator: responsible,
      });
      setSelected([]);
      setDestination("");
      setComment("");
      setResponsible("");
      if (res?.shipment) {
        setExpandedId(res.shipment.id);
      }
      setTab("archive");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!isAdmin && !isOmbor) {
    return <p className="text-center text-red-500 py-12">Ruxsat yo&apos;q</p>;
  }

  if (loading && !items.length && !groups.length) {
    return <LoadingSpinner />;
  }

  return (
    <div>
      <PageHeader
        title="Yuk chiqarish"
        subtitle="Guruhlangan yuk jo'natish va doimiy arxiv"
      />

      <div className="mb-6 flex flex-wrap gap-2">
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
          Arxiv ({groups.length})
        </button>
      </div>

      <ErrorAlert message={error} onRetry={load} />

      {tab === "dispatch" ? (
        <>
          <Card className="mb-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-bold">Tanlangan: {selected.length}</h2>
              <button
                type="button"
                onClick={selectAll}
                className="text-sm font-semibold text-blue-600"
              >
                {selected.length === items.length ? "Bekor qilish" : "Hammasini tanlash"}
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <input
                placeholder="Manzil / destination"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="rounded-2xl border px-4 py-3"
              />
              <input
                placeholder="Mas'ul operator"
                value={responsible}
                onChange={(e) => setResponsible(e.target.value)}
                className="rounded-2xl border px-4 py-3"
              />
              <input
                placeholder="Izoh"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="rounded-2xl border px-4 py-3 sm:col-span-2 lg:col-span-1"
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
            {items.length === 0 && (
              <p className="text-center text-gray-500 py-8">Omborda tayyor mahsulot yo&apos;q</p>
            )}
            {items.map((item) => (
              <label
                key={item.id}
                className={`flex cursor-pointer items-center gap-4 rounded-2xl border bg-white p-4 transition ${
                  selected.includes(item.id) ? "border-black bg-gray-50" : ""
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  onChange={() => toggle(item.id)}
                  className="h-5 w-5"
                />
                <div className="flex-1 min-w-0">
                  <p className="font-bold truncate">
                    #{item.order_id} — {item.client}
                  </p>
                  <p className="text-sm text-gray-500">{item.destination}</p>
                </div>
                <p className="font-black text-green-600 shrink-0">
                  {Number(item.amount).toLocaleString()}
                </p>
              </label>
            ))}
          </div>
        </>
      ) : (
        <>
          <Card className="mb-6">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <input
                placeholder="Qidiruv / shipment ID"
                value={filters.q}
                onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <input
                placeholder="Operator"
                value={filters.operator}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, operator: e.target.value }))
                }
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <input
                placeholder="Manzil"
                value={filters.destination}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, destination: e.target.value }))
                }
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <input
                placeholder="Mahsulot / mijoz"
                value={filters.product}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, product: e.target.value }))
                }
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, date_from: e.target.value }))
                }
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, date_to: e.target.value }))
                }
                className="rounded-xl border px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={load}
                className="rounded-xl bg-black px-4 py-2 text-sm font-bold text-white"
              >
                Qidirish
              </button>
            </div>
          </Card>

          <div className="space-y-4">
            {groups.length === 0 && (
              <p className="text-center text-gray-500 py-8">Arxiv bo&apos;sh</p>
            )}
            {groups.map((group) => (
              <Card key={group.id} className={group.deleted_at ? "opacity-60" : ""}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-black">Yuk #{group.id}</p>
                    <p className="text-sm text-gray-500">
                      {group.shipped_at
                        ? new Date(group.shipped_at).toLocaleString()
                        : ""}
                    </p>
                    <p className="text-sm">
                      <span className="font-semibold">Manzil:</span>{" "}
                      {group.destination || "—"}
                    </p>
                    <p className="text-xs text-gray-400">
                      Ombor: {group.warehouse_operator} | Mas&apos;ul:{" "}
                      {group.responsible_operator}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-green-700">
                      {group.total_products_count} ta mahsulot
                    </p>
                    {group.comment && (
                      <p className="mt-1 text-sm italic text-gray-500">{group.comment}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedId(expandedId === group.id ? null : group.id)
                      }
                      className="rounded-xl bg-gray-100 px-3 py-2 text-xs font-bold"
                    >
                      {expandedId === group.id ? "Yopish" : "Mahsulotlar"}
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadShipmentPdf(group)}
                      className="rounded-xl bg-blue-600 px-3 py-2 text-xs font-bold text-white"
                    >
                      PDF
                    </button>
                    <button
                      type="button"
                      onClick={() => printShipmentPdf(group)}
                      className="rounded-xl bg-gray-800 px-3 py-2 text-xs font-bold text-white"
                    >
                      Chop etish
                    </button>
                  </div>
                </div>

                {expandedId === group.id && (
                  <div className="mt-4 overflow-x-auto rounded-xl border">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="p-2 text-left">#</th>
                          <th className="p-2 text-left">Mijoz</th>
                          <th className="p-2 text-left">Telefon</th>
                          <th className="p-2 text-right">Summa</th>
                          <th className="p-2 text-center">Soni</th>
                          <th className="p-2 text-left">Manzil</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(group.items || []).map((item, i) => (
                          <tr key={item.id} className="border-t">
                            <td className="p-2">{i + 1}</td>
                            <td className="p-2 font-medium">{item.client}</td>
                            <td className="p-2">{item.phone}</td>
                            <td className="p-2 text-right font-bold">
                              {Number(item.amount).toLocaleString()}
                            </td>
                            <td className="p-2 text-center">{item.quantity}</td>
                            <td className="p-2">{item.product_destination}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
