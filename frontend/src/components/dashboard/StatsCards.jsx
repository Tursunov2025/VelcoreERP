export default function StatsCards({ orders }) {
  const totalOrders = orders.length;
  const completedOrders = orders.filter((item) => item.status === "Tayyor").length;
  const activeOrders = orders.filter((item) => item.status !== "Tayyor").length;
  const totalAmount = orders.reduce(
    (sum, item) => sum + Number(item.amount || 0),
    0
  );

  return (
    <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 xl:gap-6">
      <div className="rounded-[32px] bg-white p-6 shadow-lg">
        <p className="text-gray-500">Jami zakaz</p>
        <h2 className="mt-3 text-4xl font-black">{totalOrders}</h2>
      </div>

      <div className="rounded-[32px] bg-green-500 p-6 text-white shadow-lg">
        <p>Tayyor</p>
        <h2 className="mt-3 text-4xl font-black">{completedOrders}</h2>
      </div>

      <div className="rounded-[32px] bg-yellow-500 p-6 text-white shadow-lg">
        <p>Ishlab chiqarishda</p>
        <h2 className="mt-3 text-4xl font-black">{activeOrders}</h2>
      </div>

      <div className="rounded-[32px] bg-black p-6 text-white shadow-lg">
        <p>Umumiy summa</p>
        <h2 className="mt-3 text-3xl font-black md:text-4xl">
          {totalAmount.toLocaleString()} so&apos;m
        </h2>
      </div>
    </div>
  );
}
