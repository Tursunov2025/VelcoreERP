import OrderCard from "./OrderCard";

function matchesSearch(order, search) {
  const query = search.toLowerCase().trim();
  if (!query) return true;

  return (
    order.client?.toLowerCase().includes(query) ||
    order.status?.toLowerCase().includes(query) ||
    String(order.amount).includes(query) ||
    String(order.id).includes(query)
  );
}

export default function OrderList({
  orders,
  search,
  isAdmin,
  onStatusChange,
  onDelete,
}) {
  const filteredOrders = orders.filter((order) => matchesSearch(order, search));

  if (filteredOrders.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-gray-300 py-12 text-center text-gray-500">
        Zakazlar topilmadi
      </p>
    );
  }

  return (
    <div className="space-y-4 md:space-y-5">
      {filteredOrders.map((order) => (
        <OrderCard
          key={order.id}
          order={order}
          isAdmin={isAdmin}
          onStatusChange={onStatusChange}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
