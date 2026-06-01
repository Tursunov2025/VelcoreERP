export const DEFAULT_BRANDING = {
  app_name: "Velcore ERP",
  tagline: "Professional CRM / ERP tizimi",
  logo_main: "",
  logo_login: "",
  logo_sidebar: "",
  favicon: "",
  color_primary: "#000000",
  color_secondary: "#ffffff",
  color_background: "#f5f6fa",
  color_sidebar: "#000000",
  color_button: "#000000",
  color_success: "#22c55e",
  color_warning: "#f59e0b",
  color_danger: "#ef4444",
  button_radius: "16",
  button_shadow: "true",
  button_style: "rounded",
  animations_enabled: "true",
  anim_page_transitions: "true",
  anim_modals: "true",
  anim_loading: "true",
  emoji_enabled: "true",
  emoji_dashboard: "📊",
  emoji_production: "🏭",
  emoji_orders: "📋",
  emoji_warehouse: "📦",
  emoji_shipping: "🚚",
  emoji_chat: "💬",
  emoji_tasks: "✅",
  emoji_operators: "👷",
  emoji_analytics: "📈",
  emoji_finance: "💰",
  emoji_settings: "⚙️",
  emoji_llp: "📁",
  theme_mode: "light",
  language: "uz_latn",
  clock_format: "24h",
  clock_timezone: "Asia/Tashkent",
};

export const THEME_OPTIONS = [
  { id: "light", labelKey: "appearance.themeLight" },
  { id: "dark", labelKey: "appearance.themeDark" },
  { id: "auto", labelKey: "appearance.themeAuto" },
];

export const CLOCK_FORMAT_OPTIONS = [
  { id: "24h", labelKey: "appearance.clock24" },
  { id: "12h", labelKey: "appearance.clock12" },
];

export const EMOJI_NAV_KEYS = [
  { key: "emoji_dashboard", label: "Dashboard" },
  { key: "emoji_production", label: "Ishlab chiqarish" },
  { key: "emoji_orders", label: "Zakazlar" },
  { key: "emoji_warehouse", label: "Ombor" },
  { key: "emoji_shipping", label: "Yuk chiqarish" },
  { key: "emoji_chat", label: "Chat" },
  { key: "emoji_tasks", label: "Vazifalar" },
  { key: "emoji_operators", label: "Operatorlar" },
  { key: "emoji_analytics", label: "Analitika" },
  { key: "emoji_finance", label: "Moliya" },
  { key: "emoji_settings", label: "Sozlamalar" },
  { key: "emoji_llp", label: "LLP" },
];

export const COLOR_FIELDS = [
  { key: "color_primary", label: "Asosiy rang" },
  { key: "color_secondary", label: "Ikkinchi rang" },
  { key: "color_background", label: "Fon rangi" },
  { key: "color_sidebar", label: "Sidebar rangi" },
  { key: "color_button", label: "Tugma rangi" },
  { key: "color_success", label: "Muvaffaqiyat" },
  { key: "color_warning", label: "Ogohlantirish" },
  { key: "color_danger", label: "Xavf" },
];

export function isTruthy(value) {
  return String(value ?? "true").toLowerCase() in { true: 1, "1": 1, yes: 1 };
}

export function mergeBranding(data) {
  return { ...DEFAULT_BRANDING, ...(data || {}) };
}
