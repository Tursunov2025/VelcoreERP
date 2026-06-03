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

  { path: "/shipping", label: "Yuk chiqarish", iconKey: "shipping", permission: "warehouse" },

  { path: "/chat", label: "Chat", iconKey: "chat", permission: "chat" },

  { path: "/tasks", label: "Vazifalar", iconKey: "tasks", permission: "tasks" },

  { path: "/llp", label: "LLP", iconKey: "llp", permission: "llp_view" },

  { path: "/mes", label: "MES", iconKey: "mes", permission: "mes_view" },

  { path: "/materials", label: "Xom ashyo ombori", iconKey: "materials", permission: "materials_view" },

  { path: "/mes/terminal/lazer", label: "Lazer Terminal", iconKey: "lazerTerminal", permission: "mes_terminal_lazer" },

  { path: "/mes/terminal/svarshik", label: "Svarshik Terminal", iconKey: "svarshikTerminal", permission: "mes_terminal_svarshik" },

  { path: "/mes/terminal/kraska", label: "Kraska Terminal", iconKey: "kraskaTerminal", permission: "mes_terminal_kraska" },

  { path: "/mes/terminal/qc", label: "Nazorat Terminal", iconKey: "qcTerminal", permission: "mes_terminal_qc" },

  { path: "/mes/terminal/packaging", label: "Upakovka Terminal", iconKey: "packagingTerminal", permission: "mes_terminal_packaging" },

  { path: "/mes/terminal/warehouse", label: "Tayyor mahsulot ombori", iconKey: "warehouseTerminal", permission: "mes_terminal_warehouse" },

  { path: "/mes/terminal/dispatch", label: "Yuklash Terminal", iconKey: "dispatchTerminal", permission: "mes_terminal_dispatch" },

  { path: "/operators", label: "Operatorlar", iconKey: "operators", permission: "production" },

  { path: "/analytics", label: "Analitika", iconKey: "analytics", permission: "finance" },

  { path: "/finance", label: "Moliya", iconKey: "finance", permission: "finance" },

  { path: "/invoices", label: "Hisob-fakturalar", iconKey: "invoices", permission: "finance" },

];



export const ADMIN_NAV_ITEM = {

  path: "/settings",

  label: "Sozlamalar",

  iconKey: "settings",

  adminOnly: true,

  permission: "settings",

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


