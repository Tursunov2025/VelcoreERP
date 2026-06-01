import { useAuth } from "../../context/AuthContext";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import MobileNav from "./MobileNav";
import Sidebar from "./Sidebar";
import UiQuickControls from "./UiQuickControls";

export default function AppShell({ children }) {
  const { username, role, department, logout } = useAuth();
  const { branding } = useBranding();
  const { t } = useLocale();

  return (
    <div
      className="brand-page-enter flex min-h-screen"
      style={{ backgroundColor: "var(--brand-background)" }}
    >
      <Sidebar username={username} role={department || role} />
      <div className="flex min-w-0 flex-1 flex-col pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-0">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-[var(--brand-card)]/90 px-4 py-3 backdrop-blur md:hidden">
          <div>
            <p className="text-xs text-[var(--brand-muted)]">{branding.app_name}</p>
            <p className="font-bold text-[var(--brand-text)]">{username}</p>
          </div>
          <div className="flex items-center gap-2">
            <UiQuickControls compact variant="light" />
            <button
              type="button"
              onClick={logout}
              className="brand-btn px-3 py-2 text-xs text-white"
              style={{ backgroundColor: "var(--brand-danger)" }}
            >
              {t("common.logout")}
            </button>
          </div>
        </header>
        <main className="flex-1 p-4 text-[var(--brand-text)] md:p-8">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
