import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { PRODUCTION_STAGES } from "../../constants/workflow";
import ConfirmDialog from "../ui/ConfirmDialog";
import Toast from "../ui/Toast";

export default function OrdersTab() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [edit, setEdit] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [showDeleted, setShowDeleted] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.adminSearchOrders({
        include_deleted: showDeleted,
      });
      setOrders(data);
    } catch (e) {
      setToast(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [showDeleted]);

  const save = async () => {
    try {
      await api.adminUpdateOrder(edit.id, {
        client: edit.client,
        phone: edit.phone,
        amount: edit.amount,
        comment: edit.comment,
        destination: edit.destination,
        status: edit.status,
        estimated_finish_at: edit.estimated_finish_at || null,
      });
      setToast("Zakaz yangilandi");
      setEdit(null);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-black">Zakaz boshqaruvi</h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
          />
          O&apos;chirilganlar
        </label>
      </div>

      {loading ? (
        <p className="text-gray-500">Yuklanmoqda...</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <div key={order.id} className="rounded-2xl border bg-white p-4">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-bold">
                    #{order.id} {order.client}
                    {order.deleted_at && (
                      <span className="ml-2 text-xs text-red-600">[o&apos;chirilgan]</span>
                    )}
                  </p>
                  <p className="text-sm text-gray-500">
                    {order.status} · {order.destination}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEdit({ ...order })}
                    className="rounded-xl border px-3 py-1 text-sm"
                  >
                    Tahrirlash
                  </button>
                  {order.deleted_at ? (
                    <button
                      type="button"
                      onClick={async () => {
                        await api.adminRestoreOrder(order.id);
                        setToast("Tiklandi");
                        load();
                      }}
                      className="rounded-xl bg-green-600 px-3 py-1 text-sm text-white"
                    >
                      Tiklash
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setConfirm({
                          title: "O'chirish",
                          message: `Zakaz #${order.id} o'chirilsinmi?`,
                          onConfirm: async () => {
                            await api.adminDeleteOrder(order.id);
                            setToast("O'chirildi");
                            setConfirm(null);
                            load();
                          },
                        })
                      }
                      className="rounded-xl bg-red-500 px-3 py-1 text-sm text-white"
                    >
                      O&apos;chirish
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {edit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[28px] bg-white p-6">
            <h3 className="mb-4 font-black">Zakaz #{edit.id}</h3>
            <div className="space-y-3">
              {[
                ["client", "Mijoz"],
                ["phone", "Telefon"],
                ["amount", "Summa"],
                ["destination", "Manzil"],
              ].map(([key, label]) => (
                <input
                  key={key}
                  placeholder={label}
                  value={edit[key] || ""}
                  onChange={(e) => setEdit({ ...edit, [key]: e.target.value })}
                  className="w-full rounded-xl border px-4 py-3"
                />
              ))}
              <textarea
                placeholder="Izoh"
                value={edit.comment || ""}
                onChange={(e) => setEdit({ ...edit, comment: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
                rows={2}
              />
              <select
                value={edit.status}
                onChange={(e) => setEdit({ ...edit, status: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
              >
                {PRODUCTION_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <input
                type="datetime-local"
                value={
                  edit.estimated_finish_at
                    ? edit.estimated_finish_at.slice(0, 16)
                    : ""
                }
                onChange={(e) =>
                  setEdit({
                    ...edit,
                    estimated_finish_at: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null,
                  })
                }
                className="w-full rounded-xl border px-4 py-3"
              />
            </div>
            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => setEdit(null)}
                className="flex-1 rounded-xl border py-3"
              >
                Bekor
              </button>
              <button
                type="button"
                onClick={save}
                className="flex-1 rounded-xl bg-black py-3 text-white"
              >
                Saqlash
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title}
        message={confirm?.message}
        danger
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
      />
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
