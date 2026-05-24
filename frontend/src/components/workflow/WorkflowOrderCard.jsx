import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { uploadUrl } from "../../api/client";
import OrderTimeline from "./OrderTimeline";

export default function WorkflowOrderCard({ order, onComplete, onVerify, onRefresh }) {
  const { username, department, isAdmin } = useAuth();
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);

  const canAct =
    isAdmin ||
    department === order.status ||
    (department === "Tekshiruv" && order.status === "Tekshiruv");

  const handleComplete = async () => {
    setLoading(true);
    try {
      if (order.status === "Tekshiruv") {
        await onVerify(order.id, { comment });
      } else {
        await onComplete(order.id, { comment });
      }
      setComment("");
      onRefresh?.();
    } finally {
      setLoading(false);
    }
  };

  const images = order.images?.length
    ? order.images
    : order.image_url
      ? [{ url: order.image_url }]
      : [];

  return (
    <article className="rounded-[24px] border border-gray-100 bg-white p-4 shadow-md transition hover:shadow-lg">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs text-gray-400">#{order.id}</p>
          <h3 className="font-bold">{order.client}</h3>
          <p className="text-sm text-gray-500">{order.phone}</p>
        </div>
        <span className="rounded-xl bg-black px-3 py-1 text-xs font-bold text-white">
          {order.status}
        </span>
      </div>

      {order.destination && (
        <p className="mb-2 text-sm text-gray-600">📍 {order.destination}</p>
      )}
      {order.comment && (
        <p className="mb-2 text-sm italic text-gray-500">{order.comment}</p>
      )}

      <p className="mb-3 font-black text-green-600">
        {Number(order.amount).toLocaleString()} so&apos;m
      </p>

      {images.length > 0 && (
        <div className="mb-3 flex gap-2 overflow-x-auto">
          {images.map((img, i) => (
            <img
              key={i}
              src={uploadUrl(img.url)}
              alt=""
              className="h-16 w-16 shrink-0 rounded-xl object-cover"
            />
          ))}
        </div>
      )}

      <div className="mb-3 overflow-x-auto">
        <OrderTimeline history={order.history || []} />
      </div>

      {canAct && order.status !== "Tayyor" && (
        <div className="space-y-2 border-t pt-3">
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Izoh (ixtiyoriy)"
            className="w-full rounded-xl border px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={loading}
            onClick={handleComplete}
            className="w-full rounded-xl bg-black py-3 text-sm font-bold text-white transition hover:bg-gray-800 disabled:opacity-50"
          >
            {loading
              ? "..."
              : order.status === "Tekshiruv"
                ? "Tekshirildi"
                : "Tugatdim"}
          </button>
        </div>
      )}

      <p className="mt-2 text-[10px] text-gray-400">
        {order.estimated_finish_at
          ? `Tugash: ${new Date(order.estimated_finish_at).toLocaleDateString()}`
          : ""}
      </p>
    </article>
  );
}
