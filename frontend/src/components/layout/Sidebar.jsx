import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { filterNavSections, filterNavByVisibility, NAV_SECTIONS } from "../../constants/workflow";
import { useAuth } from "../../context/AuthContext";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import { useUiConfig } from "../../hooks/useUiConfig";
import OperatorTelegramLink from "../settings/OperatorTelegramLink";
import LogoutButton from "./LogoutButton";
import UiQuickControls from "./UiQuickControls";

function sectionMatches(section, pathname) {
  if (section.path === "/") return pathname === "/";
  if (pathname.startsWith(section.path)) return true;
  return (section.children || []).some(
    (child) => child.path !== "/" && pathname.startsWith(child.path)
  );
}

export default function Sidebar({ username, role }) {
  const { isAdmin, permissions } = useAuth();
  const { branding, navEmoji, assetUrl } = useBranding();
  const { t } = useLocale();
  const { config } = useUiConfig();
  const location = useLocation();
  const [openSection, setOpenSection] = useState(null);

  const navVisibility = config?.nav_visibility || {};
  let sections = filterNavSections(NAV_SECTIONS, permissions, isAdmin);
  sections = sections
    .map((section) => {
      const children = filterNavByVisibility(section.children || [], navVisibility, isAdmin);
      const sectionVisible = filterNavByVisibility(
        [{ iconKey: section.iconKey, path: section.path }],
        navVisibility,
        isAdmin
      ).length > 0;
      if (!sectionVisible && children.length === 0) return null;
      return { ...section, children: children.length ? children : section.children };
    })
    .filter(Boolean);
  const sidebarLogo = branding.logo_sidebar || branding.logo_main;

  const labelFor = (iconKey) => {
    const translated = t(`nav.${iconKey}`);
    return translated.startsWith("nav.") ? iconKey : translated;
  };

  return (
    <aside
      className="hidden w-[270px] shrink-0 flex-col p-5 text-white shadow-2xl md:flex md:rounded-r-[32px]"
      style={{ backgroundColor: "var(--brand-sidebar)" }}
    >
      {sidebarLogo ? (
        <img
          src={assetUrl(sidebarLogo)}
          alt={branding.app_name}
          className="mb-6 h-12 max-w-full object-contain object-left"
        />
      ) : (
        <h1 className="mb-6 text-3xl font-black leading-tight">{branding.app_name}</h1>
      )}
      {username && (
        <div className="mb-3 rounded-2xl bg-white/10 px-4 py-3">
          <p className="text-xs uppercase text-gray-400">{t("common.user")}</p>
          <p className="mt-1 font-semibold">{username}</p>
          <p className="text-sm capitalize text-gray-300">{role}</p>
        </div>
      )}
      <div className="mb-3">
        <UiQuickControls compact />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto pr-1">
        {sections.map((section) => {
          const emoji = navEmoji(section.iconKey) || section.emoji;
          const label = labelFor(section.iconKey);
          const hasChildren = (section.children || []).length > 1;
          const active = sectionMatches(section, location.pathname);
          const expanded = openSection === section.id || (openSection === null && active);

          if (!hasChildren) {
            return (
              <NavLink
                key={section.id}
                to={section.path}
                end={section.path === "/"}
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
                <span>{emoji}</span>
                {label}
              </NavLink>
            );
          }

          return (
            <div key={section.id}>
              <button
                type="button"
                onClick={() => setOpenSection(expanded ? "__none__" : section.id)}
                className={`flex w-full items-center justify-between gap-2 rounded-2xl px-4 py-3 text-sm transition ${
                  active ? "font-bold" : "text-gray-300 hover:bg-white/10"
                }`}
                style={
                  active
                    ? { backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }
                    : undefined
                }
              >
                <span className="flex items-center gap-3">
                  <span>{emoji}</span>
                  {label}
                </span>
                <span className="text-xs opacity-70">{expanded ? "▾" : "▸"}</span>
              </button>
              {expanded ? (
                <div className="ml-4 mt-1 space-y-1 border-l border-white/10 pl-3">
                  {section.children.map((child) => (
                    <NavLink
                      key={child.path}
                      to={child.path}
                      end={
                        child.path === section.path ||
                        child.path === "/" ||
                        section.children.some(
                          (other) => other !== child && other.path.startsWith(`${child.path}/`)
                        )
                      }
                      className={({ isActive }) =>
                        `block rounded-xl px-3 py-2 text-xs transition ${
                          isActive
                            ? "bg-white/15 font-bold text-white"
                            : "text-gray-400 hover:bg-white/10 hover:text-white"
                        }`
                      }
                    >
                      {labelFor(child.iconKey)}
                    </NavLink>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>
      <div className="mt-4 border-t border-white/10 pt-4">
        {!isAdmin && <OperatorTelegramLink />}
        <LogoutButton className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-red-500 px-4 py-3 text-sm font-bold text-white transition hover:bg-red-600" />
      </div>
    </aside>
  );
}
