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



export const NAV_ITEMS = [

  { path: "/", label: "Dashboard", iconKey: "dashboard", permission: null },

  { path: "/production", label: "Ishlab chiqarish", iconKey: "production", permission: "production" },

  { path: "/orders", label: "Zakazlar", iconKey: "orders", permission: "orders" },

  { path: "/warehouse", label: "Ombor", iconKey: "warehouse", permission: "warehouse" },

  { path: "/shipping", label: "Yuk chiqarish", iconKey: "shipping", permission: "warehouse" },

  { path: "/chat", label: "Chat", iconKey: "chat", permission: "chat" },

  { path: "/tasks", label: "Vazifalar", iconKey: "tasks", permission: "tasks" },

  { path: "/llp", label: "LLP", iconKey: "llp", permission: "llp_view" },

  { path: "/operators", label: "Operatorlar", iconKey: "operators", permission: "production" },

  { path: "/analytics", label: "Analitika", iconKey: "analytics", permission: "finance" },

  { path: "/finance", label: "Moliya", iconKey: "finance", permission: "finance" },

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

    return Boolean(permissions?.[item.permission]);

  });

}


