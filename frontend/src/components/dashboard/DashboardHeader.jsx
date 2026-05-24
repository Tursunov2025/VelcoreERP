export default function DashboardHeader({
  search,
  onSearchChange,
  isAdmin,
  onLogout,
  onAddOrder,
  onAddUser,
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <input
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Qidirish..."
        className="w-full rounded-[20px] border border-gray-300 px-5 py-4 outline-none focus:ring-2 focus:ring-black xl:max-w-md"
      />

      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto text-2xl font-black md:mr-2 md:text-3xl">Zakazlar</h2>

        <button
          type="button"
          onClick={onLogout}
          className="rounded-[20px] bg-red-500 px-5 py-3 text-white shadow-lg transition hover:bg-red-600"
        >
          Chiqish
        </button>

        <button
          type="button"
          onClick={onAddOrder}
          className="rounded-[20px] bg-black px-5 py-3 text-white shadow-lg transition hover:bg-gray-800"
        >
          + Yangi zakaz
        </button>

        {isAdmin && (
          <button
            type="button"
            onClick={onAddUser}
            className="rounded-[20px] bg-blue-600 px-5 py-3 text-white transition hover:bg-blue-700"
          >
            + User
          </button>
        )}
      </div>
    </div>
  );
}
