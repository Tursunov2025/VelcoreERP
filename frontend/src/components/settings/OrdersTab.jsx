import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { PRODUCTION_STAGES } from "../../constants/workflow";
import ConfirmDialog from "../ui/ConfirmDialog";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";

export default function OrdersTab() {
  const { t } = useLocale();
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
      setToast(t("legacySettings.orders.updated"));
      setEdit(null);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-black">{t("legacySettings.orders.title")}</h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
          />
          {t("legacySettings.orders.showDeleted")}
        </label>
      </div>

      {loading ? (
        <p className="text-gray-500">{t("common.loading")}</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <div key={order.id} className="rounded-2xl border bg-white p-4">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-bold">
                    #{order.id} {order.client}
                    {order.deleted_at && (
                      <span className="ml-2 text-xs text-red-600">[{t("legacySettings.deleted")}]</span>
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
                    {t("common.edit")}
                  </button>
                  {order.deleted_at ? (
                    <button
                      type="button"
                      onClick={async () => {
                        await api.adminRestoreOrder(order.id);
                        setToast(t("legacySettings.orders.restored"));
                        load();
                      }}
                      className="rounded-xl bg-green-600 px-3 py-1 text-sm text-white"
                    >
                      {t("platformAdministration.restore")}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setConfirm({
                          title: t("common.delete"),
                          message: t("legacySettings.orders.deleteConfirm", { id: order.id }),
                          onConfirm: async () => {
                            await api.adminDeleteOrder(order.id);
                            setToast(t("legacySettings.orders.deleted"));
                            setConfirm(null);
                            load();
                          },
                        })
                      }
                      className="rounded-xl bg-red-500 px-3 py-1 text-sm text-white"
                    >
                      {t("common.delete")}
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
            <h3 className="mb-4 font-black">{t("legacySettings.orders.orderNumber", { id: edit.id })}</h3>
            <div className="space-y-3">
              {[
                ["client", t("legacySettings.search.customer")],
                ["phone", t("organization.phone")],
                ["amount", t("legacySettings.orders.amount")],
                ["destination", t("organization.address")],
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
                placeholder={t("legacySettings.orders.comment")}
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
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={save}
                className="flex-1 rounded-xl bg-black py-3 text-white"
              >
                {t("common.save")}
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
