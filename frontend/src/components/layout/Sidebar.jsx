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
import OperatorTelegramLink from "../settings/OperatorTelegramLink";
import UiQuickControls from "./UiQuickControls";

export default function Sidebar({ username, role }) {
  const { isAdmin, permissions } = useAuth();
  const { branding, navEmoji, assetUrl } = useBranding();
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

  const sidebarLogo = branding.logo_sidebar || branding.logo_main;

  return (
    <aside
      className="hidden w-[260px] shrink-0 flex-col p-6 text-white shadow-2xl md:flex md:rounded-r-[40px]"
      style={{ backgroundColor: "var(--brand-sidebar)" }}
    >
      {sidebarLogo ? (
        <img
          src={assetUrl(sidebarLogo)}
          alt={branding.app_name}
          className="mb-8 h-12 max-w-full object-contain object-left"
        />
      ) : (
        <h1 className="mb-8 text-4xl font-black leading-tight">{branding.app_name}</h1>
      )}
      {username && (
        <div className="mb-4 rounded-2xl bg-white/10 px-4 py-3">
          <p className="text-xs uppercase text-gray-400">{t("common.user")}</p>
          <p className="mt-1 font-semibold">{username}</p>
          <p className="text-sm capitalize text-gray-300">{role}</p>
        </div>
      )}
      <div className="mb-4">
        <UiQuickControls compact />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto">
        {items.map((item) => {
          const emoji = navEmoji(item.iconKey);
          const label = t(`nav.${item.iconKey}`);
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition ${
                  isActive ? "font-bold" : "text-gray-300 hover:bg-white/10"
                }`
              }
              style={({ isActive }) =>
                isActive
                  ? { backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }
                  : undefined
              }
            >
              {emoji ? <span>{emoji}</span> : null}
              {label}
            </NavLink>
          );
        })}
      </nav>
      {!isAdmin && <OperatorTelegramLink />}
    </aside>
  );
}
