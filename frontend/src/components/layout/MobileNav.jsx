import { NavLink } from "react-router-dom";
import { ADMIN_NAV_ITEM, NAV_ITEMS } from "../../constants/workflow";
import { useAuth } from "../../context/AuthContext";

export default function MobileNav() {
  const { isAdmin } = useAuth();
  const items = isAdmin ? [...NAV_ITEMS, ADMIN_NAV_ITEM] : NAV_ITEMS;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 flex overflow-x-auto border-t border-gray-200 bg-white px-1 py-2 shadow-lg md:hidden">
      {items.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.path === "/"}
          className={({ isActive }) =>
            `flex min-w-[64px] flex-1 flex-col items-center rounded-xl px-1 py-2 text-[10px] ${
              isActive ? "bg-black text-white font-bold" : "text-gray-600"
            }`
          }
        >
          <span className="text-lg">{item.icon}</span>
          <span className="mt-1 max-w-[64px] truncate text-center">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
