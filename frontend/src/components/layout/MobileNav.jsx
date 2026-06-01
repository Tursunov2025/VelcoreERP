import { NavLink } from "react-router-dom";
import { ADMIN_NAV_ITEM, filterNavByPermissions, NAV_ITEMS } from "../../constants/workflow";
import { useAuth } from "../../context/AuthContext";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";

export default function MobileNav() {
  const { isAdmin, permissions } = useAuth();
  const { navEmoji } = useBranding();
  const { t } = useLocale();
  const baseItems = filterNavByPermissions(NAV_ITEMS, permissions, isAdmin);
  const items =
    isAdmin && permissions?.settings !== false
      ? [...baseItems, ADMIN_NAV_ITEM]
      : baseItems;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 flex overflow-x-auto border-t border-gray-200 bg-[var(--brand-card)] px-1 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pt-2 shadow-lg md:hidden">
      {items.map((item) => {
        const emoji = navEmoji(item.iconKey);
        const label = t(`nav.${item.iconKey}`);
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `flex min-w-[64px] flex-1 flex-col items-center rounded-xl px-1 py-2 text-[10px] ${
                isActive ? "font-bold text-white" : "text-[var(--brand-muted)]"
              }`
            }
            style={({ isActive }) =>
              isActive ? { backgroundColor: "var(--brand-primary)" } : undefined
            }
          >
            {emoji ? <span className="text-lg">{emoji}</span> : null}
            <span className="mt-1 max-w-[64px] truncate text-center">{label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
