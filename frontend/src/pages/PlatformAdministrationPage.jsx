import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import UiQuickControls from "../components/layout/UiQuickControls";
import { useLocale } from "../context/LocaleContext";

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
const DashboardWidgetsTab = lazy(() => import("../components/settings/DashboardWidgetsTab"));
const ProductionSettingsTab = lazy(() => import("../components/settings/ProductionSettingsTab"));
const ProductionStagesManagerTab = lazy(() => import("../components/settings/ProductionStagesManagerTab"));
const WarehouseSettingsTab = lazy(() => import("../components/settings/WarehouseSettingsTab"));
const MaterialsSettingsTab = lazy(() => import("../components/settings/MaterialsSettingsTab"));
const CostingSettingsTab = lazy(() => import("../components/settings/CostingSettingsTab"));
const TelegramTab = lazy(() => import("../components/settings/TelegramTab"));
const BackupSettingsTab = lazy(() => import("../components/settings/BackupSettingsTab"));
const MobileAppSettingsTab = lazy(() => import("../components/settings/MobileAppSettingsTab"));

function Stack({ children }) { return <div className="space-y-5">{children}</div>; }
function AppearanceWorkspace() { const { t } = useLocale(); return <Stack><AppearanceTab /><section className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5"><h2 className="text-lg font-black">{t("settingsNav.appearance")}</h2><p className="mb-4 text-sm text-[var(--brand-muted)]">{t("settings.subtitle")}</p><UiQuickControls /></section></Stack>; }
const ProductionWorkspace = () => <Stack><ProductionSettingsTab /><ProductionStagesManagerTab /></Stack>;
const WarehouseWorkspace = () => <Stack><WarehouseSettingsTab /><MaterialsSettingsTab /></Stack>;
const IntegrationsWorkspace = () => <Stack><IntegrationsTab /><TelegramTab /></Stack>;
const BackupWorkspace = () => <Stack><BackupSettingsTab /><BackupTab /></Stack>;

const sections = [
  { id:"organization", key:"organization", icon:"🏢", component:OrganizationTab, group:"foundation" },
  { id:"users", key:"users", icon:"👥", component:UsersTab, group:"access" },
  { id:"roles", key:"roles", icon:"🔐", component:RolesTab, group:"access" },
  { id:"appearance", key:"appearance", icon:"🎨", component:AppearanceWorkspace, group:"experience" },
  { id:"navigation", key:"navigation", icon:"🧭", component:NavigationTab, group:"experience" },
  { id:"dashboard", key:"dashboard", icon:"📊", component:DashboardWidgetsTab, group:"experience" },
  { id:"production", key:"production", icon:"🏭", component:ProductionWorkspace, group:"operations" },
  { id:"warehouse-materials", key:"warehouseMaterials", icon:"📦", component:WarehouseWorkspace, group:"operations" },
  { id:"costing", key:"costing", icon:"💰", component:CostingSettingsTab, group:"operations" },
  { id:"modules", key:"modules", icon:"🧩", component:ModulesTab, group:"platform" },
  { id:"integrations", key:"integrations", icon:"📲", component:IntegrationsWorkspace, group:"platform" },
  { id:"backup", key:"backup", icon:"💾", component:BackupWorkspace, group:"governance" },
  { id:"audit", key:"auditLog", icon:"📜", component:AuditTab, group:"governance" },
  { id:"security", key:"security", icon:"🔒", component:SecurityTab, group:"governance" },
  { id:"mobile", key:"mobileApp", icon:"📱", component:MobileAppSettingsTab, group:"platform" },
  { id:"system", key:"system", icon:"⚙️", component:SystemTab, group:"platform" },
  { id:"about", key:"about", icon:"ℹ️", component:AboutTab, group:"platform" },
];
const groups = ["foundation", "access", "experience", "operations", "governance", "platform"];

function TabLoading() { const { t } = useLocale(); return <div className="rounded-3xl border p-8 text-sm text-[var(--brand-muted)]">{t("common.loading")}</div>; }

export default function PlatformAdministrationPage() {
  const { t } = useLocale(); const [params,setParams]=useSearchParams();
  const requested=params.get("section")||"organization"; const active=sections.some((item)=>item.id===requested)?requested:"organization";
  const activeSection=useMemo(()=>sections.find((item)=>item.id===active),[active]); const [openGroups,setOpenGroups]=useState(()=>new Set([activeSection.group]));
  useEffect(()=>setOpenGroups((old)=>new Set([...old,activeSection.group])),[activeSection.group]); const Active=activeSection.component;
  const select=(id)=>setParams((old)=>{const next=new URLSearchParams(old);next.set("section",id);return next;},{replace:true});
  const toggle=(group)=>setOpenGroups((old)=>{const next=new Set(old);next.has(group)?next.delete(group):next.add(group);return next;});
  return <section className="mx-auto w-full max-w-7xl overflow-x-clip"><header className="mb-6 rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm sm:p-7"><h1 className="text-2xl font-black sm:text-3xl">{t("platformAdministration.title")}</h1><p className="mt-2 text-sm text-[var(--brand-muted)]">{t("platformAdministration.subtitle")}</p></header><div className="grid min-w-0 gap-5 lg:grid-cols-[270px_minmax(0,1fr)]"><nav aria-label={t("platformAdministration.categoriesLabel")} className="min-w-0 rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-3 shadow-sm lg:sticky lg:top-24 lg:h-fit">{groups.map((group)=>{const items=sections.filter((item)=>item.group===group);const open=openGroups.has(group);return <div key={group} className="mb-1"><button type="button" className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-black uppercase tracking-wide text-[var(--brand-muted)]" onClick={()=>toggle(group)}><span>{t(`platformAdministration.groups.${group}`)}</span><span>{open?"▾":"▸"}</span></button>{open?<div className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1">{items.map((item)=><button key={item.id} type="button" onClick={()=>select(item.id)} className={`flex min-w-0 items-center gap-2 rounded-2xl px-3 py-3 text-left text-sm ${item.id===active?"font-bold":"text-[var(--brand-muted)] hover:bg-black/5"}`} style={item.id===active?{backgroundColor:"var(--brand-secondary)",color:"var(--brand-primary)"}:undefined}><span>{item.icon}</span><span className="truncate">{t(`platformAdministration.${item.key}`)}</span></button>)}</div>:null}</div>})}</nav><main className="min-w-0"><Suspense fallback={<TabLoading/>}><Active/></Suspense></main></div></section>;
}
