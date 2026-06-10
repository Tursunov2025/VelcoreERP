import { useEffect, useMemo, useState } from "react";
import { API_BASE, api, getStoredTokens } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import Toast from "../components/ui/Toast";

const STATUSES = ["Draft", "Ready", "Sent", "Delivered"];

const emptyItem = {
  product_name: "",
  description: "",
  quantity: 1,
  unit: "pcs",
  weight_kg: 0,
  unit_price: 0,
};

function formatMoney(value, currency = "KZT") {
  return `${Number(value || 0).toLocaleString()} ${currency}`;
}

function statusClass(status) {
  return {
    Draft: "bg-gray-100 text-gray-700",
    Ready: "bg-blue-100 text-blue-700",
    Sent: "bg-amber-100 text-amber-700",
    Delivered: "bg-green-100 text-green-700",
  }[status] || "bg-gray-100 text-gray-700";
}

export default function ExportShipmentsPage() {
  const [shipments, setShipments] = useState([]);
  const [orders, setOrders] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [fromOrder, setFromOrder] = useState({
    order_id: "",
    country: "Kazakhstan",
    contract_number: "",
    currency: "KZT",
  });
  const [manual, setManual] = useState({
    customer: "",
    country: "Kazakhstan",
    contract_number: "",
    currency: "KZT",
    items: [{ ...emptyItem }],
  });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [list, orderList, stats] = await Promise.all([
        api.exportShipments({ status, q: search }),
        api.getOrders().catch(() => []),
        api.exportShipmentDashboard().catch(() => null),
      ]);
      setShipments(list.shipments || []);
      setOrders(orderList || []);
      setDashboard(stats);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = window.setTimeout(load, 250);
    return () => window.clearTimeout(id);
  }, [status, search]);

  const orderOptions = useMemo(
    () => orders.map((o) => ({ id: o.id, label: `#${o.id} — ${o.client} (${o.amount || 0})` })),
    [orders]
  );

  const createFromOrder = async (e) => {
    e.preventDefault();
    if (!fromOrder.order_id) return;
    try {
      await api.createExportShipmentFromOrder({
        ...fromOrder,
        order_id: Number(fromOrder.order_id),
      });
      setToast("Export shipment created from order");
      setFromOrder({ order_id: "", country: "Kazakhstan", contract_number: "", currency: "KZT" });
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const createManual = async (e) => {
    e.preventDefault();
    const items = manual.items.filter((i) => i.product_name.trim());
    if (!manual.customer.trim() || !items.length) return;
    try {
      await api.createExportShipment({ ...manual, items });
      setToast("Export shipment created");
      setManual({
        customer: "",
        country: "Kazakhstan",
        contract_number: "",
        currency: "KZT",
        items: [{ ...emptyItem }],
      });
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const updateItem = (idx, patch) => {
    setManual((prev) => ({
      ...prev,
      items: prev.items.map((item, i) => (i === idx ? { ...item, ...patch } : item)),
    }));
  };

  const generateDocs = async (shipment) => {
    setBusyId(shipment.id);
    try {
      await api.generateExportDocuments(shipment.id);
      setToast("Documents generated and attached to LLP");
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const changeStatus = async (shipment, nextStatus) => {
    setBusyId(shipment.id);
    try {
      await api.updateExportShipmentStatus(shipment.id, nextStatus);
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const downloadDoc = async (doc) => {
    const tokens = getStoredTokens();
    const res = await fetch(`${API_BASE}/export-shipments/documents/${doc.id}/download`, {
      headers: tokens?.access_token ? { Authorization: `Bearer ${tokens.access_token}` } : {},
    });
    if (!res.ok) {
      setToast("Download failed");
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = doc.filename || doc.title;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (loading && !shipments.length) return <LoadingSpinner />;

  return (
    <div>
      <BackButton fallback="/" label="Dashboard" className="mb-4" />
      <PageHeader
        title="Export Shipments"
        subtitle="Kazakhstan customers uchun invoice, packing list, specification va contract attachment"
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          ["Total", dashboard?.total ?? shipments.length],
          ["Draft", dashboard?.draft ?? 0],
          ["Ready", dashboard?.ready ?? 0],
          ["Sent", dashboard?.sent ?? 0],
          ["Delivered", dashboard?.delivered ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border bg-white p-4 shadow-sm">
            <p className="text-xs uppercase text-gray-500">{label}</p>
            <p className="mt-1 text-2xl font-black">{value}</p>
          </div>
        ))}
      </div>

      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 grid gap-4 xl:grid-cols-2">
        <form onSubmit={createFromOrder} className="rounded-3xl border bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-lg font-black">Create from existing order</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={fromOrder.order_id}
              onChange={(e) => setFromOrder((p) => ({ ...p, order_id: e.target.value }))}
              className="rounded-xl border px-3 py-2 sm:col-span-2"
            >
              <option value="">Select order</option>
              {orderOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
            <input
              value={fromOrder.country}
              onChange={(e) => setFromOrder((p) => ({ ...p, country: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Country"
            />
            <input
              value={fromOrder.contract_number}
              onChange={(e) => setFromOrder((p) => ({ ...p, contract_number: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Contract number"
            />
            <input
              value={fromOrder.currency}
              onChange={(e) => setFromOrder((p) => ({ ...p, currency: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Currency"
            />
            <button className="rounded-xl bg-black px-4 py-2 font-bold text-white">
              Create export shipment
            </button>
          </div>
        </form>

        <form onSubmit={createManual} className="rounded-3xl border bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-lg font-black">Manual shipment</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={manual.customer}
              onChange={(e) => setManual((p) => ({ ...p, customer: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Customer"
            />
            <input
              value={manual.contract_number}
              onChange={(e) => setManual((p) => ({ ...p, contract_number: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Contract number"
            />
            <input
              value={manual.country}
              onChange={(e) => setManual((p) => ({ ...p, country: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Country"
            />
            <input
              value={manual.currency}
              onChange={(e) => setManual((p) => ({ ...p, currency: e.target.value }))}
              className="rounded-xl border px-3 py-2"
              placeholder="Currency"
            />
          </div>
          <div className="mt-3 space-y-2">
            {manual.items.map((item, idx) => (
              <div key={idx} className="grid gap-2 rounded-2xl bg-gray-50 p-3 sm:grid-cols-5">
                <input
                  value={item.product_name}
                  onChange={(e) => updateItem(idx, { product_name: e.target.value })}
                  className="rounded-xl border px-3 py-2 sm:col-span-2"
                  placeholder="Product"
                />
                <input
                  type="number"
                  value={item.quantity}
                  onChange={(e) => updateItem(idx, { quantity: Number(e.target.value) })}
                  className="rounded-xl border px-3 py-2"
                  placeholder="Qty"
                />
                <input
                  type="number"
                  value={item.weight_kg}
                  onChange={(e) => updateItem(idx, { weight_kg: Number(e.target.value) })}
                  className="rounded-xl border px-3 py-2"
                  placeholder="Kg"
                />
                <input
                  type="number"
                  value={item.unit_price}
                  onChange={(e) => updateItem(idx, { unit_price: Number(e.target.value) })}
                  className="rounded-xl border px-3 py-2"
                  placeholder="Price"
                />
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setManual((p) => ({ ...p, items: [...p.items, { ...emptyItem }] }))}
              className="rounded-xl border px-4 py-2"
            >
              + Product
            </button>
            <button className="rounded-xl bg-black px-4 py-2 font-bold text-white">Create</button>
          </div>
        </form>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-2xl border px-4 py-3 sm:max-w-md"
          placeholder="Search shipment/customer/contract..."
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-2xl border px-4 py-3 sm:w-56"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="space-y-4">
        {shipments.map((shipment) => (
          <div key={shipment.id} className="rounded-3xl border bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-black">{shipment.shipment_number}</h2>
                  <span className={`rounded-full px-3 py-1 text-xs font-bold ${statusClass(shipment.status)}`}>
                    {shipment.status}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-500">
                  {shipment.customer} • {shipment.country} • Contract {shipment.contract_number || "—"}
                </p>
                <p className="mt-2 text-sm">
                  Qty {shipment.total_quantity || 0} • Weight {shipment.total_weight || 0} kg •{" "}
                  {formatMoney(shipment.total_amount, shipment.currency)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId === shipment.id}
                  onClick={() => generateDocs(shipment)}
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-60"
                >
                  Generate docs
                </button>
                <select
                  value={shipment.status}
                  disabled={busyId === shipment.id}
                  onChange={(e) => changeStatus(shipment, e.target.value)}
                  className="rounded-xl border px-3 py-2 text-sm"
                >
                  {STATUSES.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div className="rounded-2xl bg-gray-50 p-3">
                <p className="mb-2 text-sm font-bold">Products</p>
                {shipment.items.map((item) => (
                  <div key={item.id} className="mb-2 text-sm last:mb-0">
                    <b>{item.product_name}</b> — {item.quantity} {item.unit}, {item.weight_kg} kg,{" "}
                    {formatMoney(item.total_amount, shipment.currency)}
                  </div>
                ))}
              </div>
              <div className="rounded-2xl bg-gray-50 p-3">
                <p className="mb-2 text-sm font-bold">Documents attached to LLP</p>
                {shipment.documents.length ? (
                  <div className="flex flex-wrap gap-2">
                    {shipment.documents.map((doc) => (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() => downloadDoc(doc)}
                        className="rounded-xl border bg-white px-3 py-2 text-xs hover:bg-gray-100"
                      >
                        {doc.title}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No generated documents yet.</p>
                )}
              </div>
            </div>
          </div>
        ))}
        {!shipments.length && !loading ? (
          <p className="rounded-2xl border bg-white p-8 text-center text-gray-500">
            Export shipments not found.
          </p>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}

