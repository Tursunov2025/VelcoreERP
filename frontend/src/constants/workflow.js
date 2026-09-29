export const PRODUCTION_STAGES = [

  "Kesish",

  "Svarka",

  "Kraska",

  "Upakovka",

  "Tekshiruv",

  "Tayyor",

];



export const WORKFLOW_STAGES = PRODUCTION_STAGES.filter((s) => s !== "Tayyor");



export const DEPARTMENTS = [

  "Kesish",

  "Svarka",

  "Kraska",

  "Upakovka",

  "Tekshiruv",

  "Ombor",

  "Admin",

];



export const STATUS_COLORS = {

  Kesish: "bg-amber-500",

  Svarka: "bg-orange-500",

  Kraska: "bg-purple-500",

  Upakovka: "bg-pink-500",

  Tekshiruv: "bg-blue-500",

  Tayyor: "bg-green-500",

};



export const MES_ANY_PERMISSIONS = [
  "mes_view",
  "mes_edit",
  "mes_terminal_lazer",
  "mes_terminal_svarshik",
  "mes_terminal_kraska",
  "mes_terminal_qc",
  "mes_terminal_packaging",
  "mes_terminal_warehouse",
  "mes_terminal_dispatch",
];

export const NAV_ITEMS = [

  { path: "/", label: "Dashboard", iconKey: "dashboard", permission: null },

  { path: "/production", label: "Ishlab chiqarish", iconKey: "production", permission: "production" },

  { path: "/orders", label: "Zakazlar", iconKey: "orders", permission: "orders" },

  { path: "/warehouse", label: "Ombor", iconKey: "warehouse", permission: "warehouse" },

  { path: "/chat", label: "Chat", iconKey: "chat", permission: "chat" },

  { path: "/tasks", label: "Vazifalar", iconKey: "tasks", permission: "tasks" },

  { path: "/logistics", label: "Export va Logistika", iconKey: "exportLogistics", permission: "export_view" },

  { path: "/crm", label: "CRM", iconKey: "crm", permission: "orders" },

  { path: "/currencies", label: "Valyutalar", iconKey: "currencies", permission: "finance" },

  { path: "/materials/forecast", label: "Ombor prognozi", iconKey: "forecast", permission: "materials_view" },

  { path: "/mes", label: "MES", iconKey: "mes", permission: "mes_view" },

  { path: "/materials", label: "Xom ashyo ombori", iconKey: "materials", permission: "materials_view" },

  { path: "/mes/terminal/lazer", label: "Lazer Terminal", iconKey: "lazerTerminal", permission: "mes_terminal_lazer" },

  { path: "/mes/terminal/svarshik", label: "Svarshik Terminal", iconKey: "svarshikTerminal", permission: "mes_terminal_svarshik" },

  { path: "/mes/terminal/kraska", label: "Kraska Terminal", iconKey: "kraskaTerminal", permission: "mes_terminal_kraska" },

  { path: "/mes/terminal/qc", label: "Nazorat Terminal", iconKey: "qcTerminal", permission: "mes_terminal_qc" },

  { path: "/mes/terminal/packaging", label: "Upakovka Terminal", iconKey: "packagingTerminal", permission: "mes_terminal_packaging" },

  { path: "/mes/terminal/warehouse", label: "Tayyor mahsulot ombori", iconKey: "warehouseTerminal", permission: "mes_terminal_warehouse" },

  { path: "/operators", label: "Operatorlar", iconKey: "operators", permission: "production" },

  { path: "/analytics", label: "Analitika", iconKey: "analytics", permission: "finance" },

  { path: "/finance", label: "Moliya", iconKey: "finance", permission: "finance" },

  { path: "/invoices", label: "Hisob-fakturalar", iconKey: "invoices", permission: "finance" },

];



/**
 * Phase 11B — Variant B grouped sidebar.
 * Each section has a default emoji (used when branding emoji is not set),
 * a primary path and optional children rendered as a collapsible group.
 * Section is visible when at least one of its items passes permission filters.
 */
const DISPLAY_CENTER_SECTION = {
  id: "displayCenter",
  iconKey: "displayCenter",
  emoji: "📺",
  path: "/display-center",
  adminOnly: true,
  permission: "settings",
  children: [
    { path: "/display-center", iconKey: "displayDashboard", adminOnly: true, permission: "settings" },
    { path: "/display-center/displays", iconKey: "displayDisplays", adminOnly: true, permission: "settings" },
    { path: "/display-center/playlists", iconKey: "displayPlaylists", adminOnly: true, permission: "settings" },
    { path: "/display-center/widgets", iconKey: "displayWidgets", adminOnly: true, permission: "settings" },
    { path: "/display-center/media", iconKey: "displayMediaLibrary", adminOnly: true, permission: "settings" },
    { path: "/display-center/templates", iconKey: "displayTemplates", adminOnly: true, permission: "settings" },
    { path: "/display-center/designer", iconKey: "displayDesigner", adminOnly: true, permission: "settings" },
    { path: "/display-center/scheduler", iconKey: "displayScheduler", adminOnly: true, permission: "settings" },
    { path: "/display-center/monitoring", iconKey: "displayMonitoring", adminOnly: true, permission: "settings" },
    { path: "/display-center/settings", iconKey: "displaySettings", adminOnly: true, permission: "settings" },
  ],
};

const TRACEABILITY_SECTION = {
  id: "traceability",
  iconKey: "traceability",
  emoji: "🔖",
  path: "/traceability",
  permission: "traceability_view",
};

export const NAV_SECTIONS = [
  {
    id: "dashboard",
    iconKey: "dashboard",
    emoji: "🏠",
    path: "/",
    permission: null,
  },
  {
    id: "platformAdministration",
    iconKey: "platformAdministration",
    emoji: "⚙️",
    path: "/admin",
    permission: "platform_admin_view",
  },
  DISPLAY_CENTER_SECTION,
  TRACEABILITY_SECTION,
  {
    id: "crm",
    iconKey: "crm",
    emoji: "👥",
    path: "/crm",
    permission: "orders",
    children: [
      { path: "/crm", iconKey: "crmLedger", permission: "orders" },
      { path: "/chat", iconKey: "chat", permission: "chat" },
      { path: "/tasks", iconKey: "tasks", permission: "tasks" },
    ],
  },
  {
    id: "productionProjects",
    iconKey: "productionProjects",
    emoji: "🏭",
    path: "/production-projects",
    permission: "production_projects_view",
    children: [
      { path: "/production-projects", iconKey: "productionProjects", permission: "production_projects_view" },
      { path: "/mes", iconKey: "mes", permission: "mes_view" },
      { path: "/operators", iconKey: "operators", permission: "production" },
    ],
  },
  {
    id: "technology",
    iconKey: "technology",
    emoji: "📋",
    path: "/mes/templates",
    permission: "mes_view",
    children: [
      { path: "/mes/templates", iconKey: "mesTemplates", permission: "mes_view" },
      { path: "/mes/parts", iconKey: "mesParts", permission: "mes_view" },
      { path: "/materials/part-bom", iconKey: "materialsBom", permission: "materials_view" },
    ],
  },
  {
    id: "warehouse",
    iconKey: "warehouse",
    emoji: "📦",
    path: "/warehouse",
    permission: "warehouse",
    children: [
      { path: "/warehouse", iconKey: "warehouse", permission: "warehouse" },
      { path: "/mes/finished-warehouse", iconKey: "finishedProductWarehouse", permission: "mes_terminal_warehouse" },
      { path: "/materials", iconKey: "materials", permission: "materials_view" },
      { path: "/materials/forecast", iconKey: "forecast", permission: "materials_view" },
      { path: "/mes/terminal/warehouse", iconKey: "warehouseTerminal", permission: "mes_terminal_warehouse" },
    ],
  },
  {
    id: "exportLogistics",
    iconKey: "exportLogistics",
    emoji: "🚚",
    path: "/logistics",
    permission: "export_view",
    children: [
      { path: "/logistics", iconKey: "logisticsDashboard", permission: "export_view" },
      { path: "/logistics/shipments", iconKey: "shipments", permission: "export_view" },
      { path: "/logistics/loading", iconKey: "loadingPlans", permission: "export_view" },
      { path: "/logistics/transport", iconKey: "transport", permission: "export_view" },
      { path: "/logistics/drivers", iconKey: "drivers", permission: "export_view" },
      { path: "/logistics/gps", iconKey: "gpsMonitoring", permission: "export_view" },
      { path: "/logistics/gps/tasks", iconKey: "gpsTasks", permission: "export_view" },
      { path: "/logistics/delivery-history", iconKey: "deliveryHistory", permission: "export_view" },
    ],
  },
  {
    id: "finance",
    iconKey: "finance",
    emoji: "💰",
    path: "/finance",
    permission: "finance",
    children: [
      { path: "/finance", iconKey: "finance", permission: "finance" },
      { path: "/currencies", iconKey: "currencies", permission: "finance" },
      { path: "/analytics", iconKey: "analytics", permission: "finance" },
      { path: "/invoices", iconKey: "invoices", permission: "finance" },
    ],
  },
];

function itemAllowed(item, permissions, isAdmin) {
  if (item.hidden) return false;
  if (item.adminOnly && !isAdmin) return false;
  if (!item.permission) return true;
  if (isAdmin) return true;
  if (item.iconKey === "mes") {
    return MES_ANY_PERMISSIONS.some((key) => Boolean(permissions?.[key]));
  }
  return Boolean(permissions?.[item.permission]);
}

/** Filter grouped sections: section stays if its main path or any child is allowed. */
export function filterNavSections(sections, permissions, isAdmin) {
  return sections
    .map((section) => {
      const children = (section.children || []).filter((child) =>
        itemAllowed(child, permissions, isAdmin)
      );
      const selfAllowed = itemAllowed(section, permissions, isAdmin);
      if (!selfAllowed && children.length === 0) return null;
      return { ...section, children };
    })
    .filter(Boolean);
}

export const ADMIN_NAV_ITEM = {

  path: "/admin",

  label: "Platform Administration",

  iconKey: "platformAdministration",

  adminOnly: true,

  permission: "platform_admin_view",

};



export function filterNavByPermissions(items, permissions, isAdmin) {

  return items.filter((item) => {

    if (item.adminOnly && !isAdmin) return false;

    if (!item.permission) return true;

    if (isAdmin) return true;

    if (item.iconKey === "mes") {
      return MES_ANY_PERMISSIONS.some((key) => Boolean(permissions?.[key]));
    }

    return Boolean(permissions?.[item.permission]);

  });

}



/** Apply Super Admin menu visibility map (iconKey → visible). */
export function filterNavByVisibility(items, navVisibility, isAdmin) {
  if (!navVisibility || isAdmin) return items;
  return items.filter((item) => {
    const key = item.iconKey;
    if (!key) return true;
    return navVisibility[key] !== false;
  });
}


