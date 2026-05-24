import { useEffect, useState } from "react";
import { api } from "../../api/client";
import Card from "../ui/Card";
import ErrorAlert from "../ui/ErrorAlert";
import LoadingSpinner from "../ui/LoadingSpinner";
import { downloadShipmentPdf } from "../../utils/shipmentGroupPdf";

export default function ShipmentsArchiveTab() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showDeleted, setShowDeleted] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getShipmentGroups({
        include_deleted: showDeleted,
      });
      setGroups(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [showDeleted]);

  const softDelete = async (id) => {
    if (!window.confirm(`Yuk #${id} ni arxivdan o'chirish?`)) return;
    try {
      await api.adminDeleteShipmentGroup(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const restore = async (id) => {
    try {
      await api.adminRestoreShipmentGroup(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading && !groups.length) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Yuk arxivi boshqaruvi</h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
          />
          O&apos;chirilgan yuklar
        </label>
      </div>
      <ErrorAlert message={error} onRetry={load} />
      <div className="space-y-3">
        {groups.map((g) => (
          <Card key={g.id} className={g.deleted_at ? "border-red-200 bg-red-50/30" : ""}>
            <div className="flex flex-wrap justify-between gap-2">
              <div>
                <p className="font-bold">
                  Yuk #{g.id}
                  {g.deleted_at && (
                    <span className="ml-2 text-xs text-red-600">(o&apos;chirilgan)</span>
                  )}
                </p>
                <p className="text-sm text-gray-500">
                  {g.shipped_at ? new Date(g.shipped_at).toLocaleString() : ""} —{" "}
                  {g.destination}
                </p>
                <p className="text-xs text-gray-400">
                  {g.warehouse_operator} | {g.total_products_count} mahsulot
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => downloadShipmentPdf(g)}
                  className="rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-bold text-white"
                >
                  PDF
                </button>
                {g.deleted_at ? (
                  <button
                    type="button"
                    onClick={() => restore(g.id)}
                    className="rounded-xl bg-green-600 px-3 py-1.5 text-xs font-bold text-white"
                  >
                    Tiklash
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => softDelete(g.id)}
                    className="rounded-xl bg-red-600 px-3 py-1.5 text-xs font-bold text-white"
                  >
                    O&apos;chirish
                  </button>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
