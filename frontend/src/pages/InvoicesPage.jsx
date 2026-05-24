import { useEffect, useState } from "react";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { downloadInvoice, printInvoice } from "../utils/invoicePdf";

export default function InvoicesPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setOrders(await api.getOrders());
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
      <PageHeader
        title="Invoyslar"
        subtitle="PDF eksport, QR kod va barcode"
      />
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-4">
        {orders.map((order) => (
          <Card key={order.id}>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-bold">#{order.id} — {order.client}</p>
                <p className="text-sm text-gray-500">
                  {Number(order.amount).toLocaleString()} so&apos;m — {order.status}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => downloadInvoice(order)}
                  className="rounded-2xl bg-black px-5 py-3 text-sm text-white"
                >
                  PDF yuklab olish
                </button>
                <button
                  type="button"
                  onClick={() => printInvoice(order)}
                  className="rounded-2xl border border-black px-5 py-3 text-sm"
                >
                  Chop etish
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
