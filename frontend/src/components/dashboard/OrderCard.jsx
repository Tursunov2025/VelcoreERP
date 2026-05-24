import { ORDER_STATUSES, STATUS_COLORS } from "../../constants/orderStatuses";

export default function OrderCard({
  order,
  isAdmin,
  onStatusChange,
  onDelete,
}) {
  const statusClass = STATUS_COLORS[order.status] || "bg-gray-500";

  return (
    <article className="flex flex-col justify-between gap-4 rounded-[28px] border border-gray-200 p-5 transition hover:shadow-lg md:flex-row md:items-center md:gap-6 md:p-6">
      <div className="min-w-0">
        <h3 className="text-lg font-bold md:text-xl">#{order.id}</h3>
        <p className="mt-1 truncate text-gray-500">{order.client}</p>
        {order.phone && (
          <p className="mt-1 text-sm text-gray-400">{order.phone}</p>
        )}
      </div>

      <select
        value={order.status}
        onChange={(e) => onStatusChange(order.id, e.target.value)}
        className={`rounded-2xl px-4 py-3 text-white outline-none ${statusClass}`}
      >
        {ORDER_STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>

      <div className="flex items-center justify-between gap-4 md:justify-end md:gap-5">
        <div className="text-lg font-black text-green-600 md:text-xl">
          {Number(order.amount).toLocaleString()} so&apos;m
        </div>

        {isAdmin && (
          <button
            type="button"
            onClick={() => onDelete(order.id)}
            className="shrink-0 rounded-2xl bg-red-500 px-5 py-3 text-white transition hover:bg-red-600"
          >
            O&apos;chirish
          </button>
        )}
      </div>
    </article>
  );
}
