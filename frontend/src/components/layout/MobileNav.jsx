import { useState } from "react";
import { NavLink } from "react-router-dom";
import { CONTROL_CENTER_NAV_ITEM } from "../../constants/controlCenter";
import {
  ADMIN_NAV_ITEM,
  filterNavByPermissions,
  filterNavByVisibility,
  NAV_ITEMS,
} from "../../constants/workflow";
import { useAuth } from "../../context/AuthContext";
import { useUiConfig } from "../../hooks/useUiConfig";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import LogoutButton from "./LogoutButton";

export default function MobileNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { isAdmin, permissions } = useAuth();
  const { navEmoji } = useBranding();
  const { t } = useLocale();
  const { config } = useUiConfig();
  let baseItems = filterNavByPermissions(NAV_ITEMS, permissions, isAdmin);
  baseItems = filterNavByVisibility(baseItems, config?.nav_visibility, isAdmin);
  const items = [];
  if (isAdmin) {
    items.push(...baseItems, CONTROL_CENTER_NAV_ITEM);
    if (permissions?.settings !== false) items.push(ADMIN_NAV_ITEM);
  } else {
    items.push(...baseItems);
  }
  const fixedItems = [
    items.find((item) => item.path === "/") || { path: "/", iconKey: "dashboard" },
    items.find((item) => item.path === "/orders") || { path: "/orders", iconKey: "orders" },
    items.find((item) => item.path === "/mes") || { path: "/mes", iconKey: "mes" },
    items.find((item) => item.path === "/warehouse") || { path: "/warehouse", iconKey: "warehouse" },
  ];

  return (
    <>
      {menuOpen ? (
        <div className="fixed inset-0 z-50 bg-black/40 md:hidden" onClick={() => setMenuOpen(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[78vh] rounded-t-3xl bg-[var(--brand-card)] p-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-black">Menu</h2>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="rounded-full border px-3 py-1 text-sm"
              >
                ×
              </button>
            </div>
            <div className="grid max-h-[52vh] grid-cols-2 gap-2 overflow-y-auto pb-3">
              {items.map((item) => {
                const emoji = navEmoji(item.iconKey);
                const label = t(`nav.${item.iconKey}`);
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === "/"}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      `rounded-2xl border px-3 py-3 text-sm ${
                        isActive ? "font-bold text-white" : "text-[var(--brand-text)]"
                      }`
                    }
                    style={({ isActive }) =>
                      isActive ? { backgroundColor: "var(--brand-primary)" } : undefined
                    }
                  >
                    <span className="mr-2">{emoji}</span>
                    {label}
                  </NavLink>
                );
              })}
            </div>
            <LogoutButton className="w-full rounded-2xl bg-red-500 px-4 py-3 text-sm font-bold text-white" />
          </div>
        </div>
      ) : null}
      <nav className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-5 gap-1 border-t border-gray-200 bg-[var(--brand-card)] px-1 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pt-2 shadow-lg md:hidden">
        {fixedItems.map((item) => {
          const emoji = navEmoji(item.iconKey);
          const label = t(`nav.${item.iconKey}`);
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex min-w-0 flex-col items-center rounded-xl px-1 py-2 text-[10px] ${
                  isActive ? "font-bold text-white" : "text-[var(--brand-muted)]"
                }`
              }
              style={({ isActive }) =>
                isActive ? { backgroundColor: "var(--brand-primary)" } : undefined
              }
            >
              {emoji ? <span className="text-lg">{emoji}</span> : null}
              <span className="mt-1 max-w-full truncate text-center">{label}</span>
            </NavLink>
          );
        })}
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          className="flex min-w-0 flex-col items-center rounded-xl px-1 py-2 text-[10px] text-[var(--brand-muted)]"
        >
          <span className="text-lg">☰</span>
          <span className="mt-1 max-w-full truncate text-center">Menu</span>
        </button>
      </nav>
    </>
  );
}
