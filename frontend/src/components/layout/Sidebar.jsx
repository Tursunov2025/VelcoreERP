import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../constants/orderStatuses";

export default function Sidebar({ username, role }) {
  return (
    <aside className="hidden w-[260px] shrink-0 flex-col bg-black p-6 text-white shadow-2xl md:flex md:rounded-r-[40px]">
      <h1 className="mb-8 text-4xl font-black leading-tight">Azmus ERP</h1>
      {username && (
        <div className="mb-6 rounded-2xl bg-white/10 px-4 py-3">
          <p className="text-xs uppercase text-gray-400">Foydalanuvchi</p>
          <p className="mt-1 font-semibold">{username}</p>
          <p className="text-sm capitalize text-gray-300">{role}</p>
        </div>
      )}
      <nav className="flex-1 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition ${
                isActive ? "bg-white text-black font-bold" : "text-gray-300 hover:bg-white/10"
              }`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
