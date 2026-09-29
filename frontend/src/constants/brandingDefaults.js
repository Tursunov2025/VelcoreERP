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
  color_button_text: "#ffffff",
  color_secondary_button: "#ffffff",
  color_secondary_button_text: "#111827",
  color_card: "#ffffff",
  color_sidebar_text: "#ffffff",
  color_sidebar_active: "#ffffff",
  color_sidebar_active_text: "#111827",
  color_header: "#ffffff",
  color_heading: "#111827",
  color_text: "#111827",
  color_muted: "#6b7280",
  color_link: "#2563eb",
  color_input_background: "#ffffff",
  color_input_text: "#111827",
  color_input_border: "#d1d5db",
  color_table_header: "#f8fafc",
  color_table_header_text: "#475569",
  color_table_row: "#ffffff",
  color_border: "#e5e7eb",
  color_success: "#22c55e",
  color_warning: "#f59e0b",
  color_danger: "#ef4444",
  color_info: "#3b82f6",
  color_focus: "#2563eb",
  font_scale: "1",
  reduced_motion: "false",
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
  emoji_mes: "🏭",
  emoji_materials: "🧱",
  emoji_controlCenter: "🎛️",
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
  { key: "emoji_mes", label: "MES" },
  { key: "emoji_materials", label: "Xom ashyo ombori" },
  { key: "emoji_controlCenter", label: "Control Center" },
];

export const COLOR_FIELDS = [
  "color_primary", "color_button", "color_button_text", "color_secondary_button", "color_secondary_button_text",
  "color_background", "color_card", "color_sidebar", "color_sidebar_text", "color_sidebar_active", "color_sidebar_active_text",
  "color_header", "color_heading", "color_text", "color_muted", "color_link", "color_input_background", "color_input_text",
  "color_input_border", "color_table_header", "color_table_header_text", "color_table_row", "color_border", "color_success",
  "color_warning", "color_danger", "color_info", "color_focus",
].map((key) => ({ key, labelKey: `appearance.colors.${key}` }));

export function isTruthy(value) {
  return String(value ?? "true").toLowerCase() in { true: 1, "1": 1, yes: 1 };
}

export function mergeBranding(data) {
  return { ...DEFAULT_BRANDING, ...(data || {}) };
}
