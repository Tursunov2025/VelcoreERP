import { lazy, Suspense, useMemo, useState } from "react";

const OrganizationTab = lazy(() => import("../components/platformAdministration/OrganizationTab"));
const UsersTab = lazy(() => import("../components/platformAdministration/UsersTab"));
const RolesTab = lazy(() => import("../components/platformAdministration/RolesTab"));
const AppearanceTab = lazy(() => import("../components/platformAdministration/AppearanceTab"));
const NavigationTab = lazy(() => import("../components/platformAdministration/NavigationTab"));
const ModulesTab = lazy(() => import("../components/platformAdministration/ModulesTab"));
const IntegrationsTab = lazy(() => import("../components/platformAdministration/IntegrationsTab"));
const BackupTab = lazy(() => import("../components/platformAdministration/BackupTab"));
const AuditTab = lazy(() => import("../components/platformAdministration/AuditTab"));
const SecurityTab = lazy(() => import("../components/platformAdministration/SecurityTab"));
const SystemTab = lazy(() => import("../components/platformAdministration/SystemTab"));
const AboutTab = lazy(() => import("../components/platformAdministration/AboutTab"));

const categories = [
  { id: "organization", label: "Organization", icon: "🏢", component: OrganizationTab },
  { id: "users", label: "Users", icon: "👥", component: UsersTab },
  { id: "roles", label: "Roles & Permissions", icon: "🔐", component: RolesTab },
  { id: "appearance", label: "Appearance", icon: "🎨", component: AppearanceTab },
  { id: "navigation", label: "Navigation", icon: "🧭", component: NavigationTab },
  { id: "modules", label: "Modules", icon: "🧩", component: ModulesTab },
  { id: "integrations", label: "Integrations", icon: "📲", component: IntegrationsTab },
  { id: "backup", label: "Backup", icon: "💾", component: BackupTab },
  { id: "audit", label: "Audit Log", icon: "📜", component: AuditTab },
  { id: "security", label: "Security", icon: "🔒", component: SecurityTab },
  { id: "system", label: "System", icon: "⚙️", component: SystemTab },
  { id: "about", label: "About", icon: "ℹ️", component: AboutTab },
];

function TabLoading() {
  return <div className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-8 text-sm text-[var(--brand-muted)]">Loading administration area…</div>;
}

export default function PlatformAdministrationPage() {
  const [activeId, setActiveId] = useState("organization");
  const activeCategory = useMemo(
    () => categories.find((category) => category.id === activeId) || categories[0],
    [activeId]
  );
  const ActiveTab = activeCategory.component;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <div className="mb-6 rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm sm:p-7">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand-muted)]">Enterprise control plane</p>
        <h1 className="mt-2 text-2xl font-black text-[var(--brand-text)] sm:text-3xl">Platform Administration</h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--brand-muted)]">A centralized administration workspace for governing the Velcore ERP platform.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[270px_minmax(0,1fr)]">
        <nav aria-label="Platform Administration categories" className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-3 shadow-sm lg:sticky lg:top-24 lg:h-fit">
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1">
            {categories.map((category) => {
              const selected = category.id === activeCategory.id;
              return (
                <button key={category.id} type="button" onClick={() => setActiveId(category.id)} className={`flex items-center gap-3 rounded-2xl px-3 py-3 text-left text-sm transition ${selected ? "font-bold" : "text-[var(--brand-muted)] hover:bg-black/5 dark:hover:bg-white/10"}`} style={selected ? { backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" } : undefined}>
                  <span aria-hidden="true" className="text-base">{category.icon}</span>
                  <span>{category.label}</span>
                </button>
              );
            })}
          </div>
        </nav>

        <Suspense fallback={<TabLoading />}>
          <ActiveTab />
        </Suspense>
      </div>
    </section>
  );
}
