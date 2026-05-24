const NAV_ITEMS = ["Dashboard", "Zakazlar", "Ishlab chiqarish", "Ombor"];

export default function Sidebar({ username, role }) {
  return (
    <aside className="flex w-[90px] shrink-0 flex-col bg-black p-4 text-white shadow-2xl md:w-[260px] md:rounded-r-[40px] md:p-6">
      <h1 className="mb-8 text-lg font-black leading-tight tracking-tight md:mb-14 md:text-5xl">
        <span className="md:hidden">Azmus</span>
        <span className="hidden md:inline">Azmus furniture</span>
      </h1>

      {username && (
        <div className="mb-6 hidden rounded-2xl bg-white/10 px-4 py-3 md:block">
          <p className="text-xs uppercase tracking-wide text-gray-400">Foydalanuvchi</p>
          <p className="mt-1 truncate font-semibold">{username}</p>
          <p className="mt-1 text-sm capitalize text-gray-300">{role}</p>
        </div>
      )}

      <nav className="mt-4 space-y-3 md:mt-10 md:space-y-5">
        {NAV_ITEMS.map((item) => (
          <span
            key={item}
            className="hidden cursor-default rounded-xl px-2 py-1 text-sm text-gray-300 md:block md:text-base"
          >
            {item}
          </span>
        ))}
      </nav>
    </aside>
  );
}
