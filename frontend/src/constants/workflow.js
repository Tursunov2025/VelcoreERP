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
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/production", label: "Ishlab chiqarish", icon: "🏭" },
  { path: "/orders", label: "Zakazlar", icon: "📋" },
  { path: "/warehouse", label: "Ombor", icon: "📦" },
  { path: "/shipping", label: "Yuk chiqarish", icon: "🚚" },
  { path: "/operators", label: "Operatorlar", icon: "👷" },
  { path: "/analytics", label: "Analitika", icon: "📈" },
  { path: "/finance", label: "Moliya", icon: "💰" },
];
