import { getApiBase } from "../api/client";
import { isTruthy, mergeBranding } from "../constants/brandingDefaults";

const DARK_SURFACE_TOKENS = {
  color_background: "#0f172a", color_card: "#111827", color_header: "#111827",
  color_heading: "#f8fafc", color_text: "#e5e7eb", color_muted: "#94a3b8",
  color_secondary_button: "#1f2937", color_secondary_button_text: "#f8fafc",
  color_input_background: "#111827", color_input_text: "#f8fafc", color_input_border: "#334155",
  color_table_header: "#1e293b", color_table_header_text: "#e2e8f0",
  color_table_row: "#111827", color_border: "#334155",
};

function resolveAssetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  const base = getApiBase().replace(/\/$/, "");
  return `${base}${url.startsWith("/") ? url : `/${url}`}`;
}

export function resolveEffectiveTheme(themeMode) {
  if (themeMode === "auto" || themeMode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return themeMode === "dark" ? "dark" : "light";
}

export function applyBrandingToElement(branding, element, effectiveTheme = "light") {
  const b = mergeBranding(branding);
  const color = (key) => effectiveTheme === "dark" && DARK_SURFACE_TOKENS[key]
    ? DARK_SURFACE_TOKENS[key]
    : b[key];
  const radius =
    b.button_style === "square"
      ? "4px"
      : `${Math.max(0, Number(b.button_radius) || 16)}px`;
  const shadow = isTruthy(b.button_shadow)
    ? "0 4px 14px rgba(0,0,0,0.12)"
    : "none";
  const animOn = isTruthy(b.animations_enabled);

  element.style.setProperty("--brand-primary", b.color_primary);
  element.style.setProperty("--brand-secondary", b.color_secondary);
  element.style.setProperty("--brand-background", color("color_background"));
  element.style.setProperty("--brand-sidebar", b.color_sidebar);
  element.style.setProperty("--brand-button", b.color_button);
  element.style.setProperty("--brand-button-text", b.color_button_text);
  element.style.setProperty("--brand-secondary-button", color("color_secondary_button"));
  element.style.setProperty("--brand-secondary-button-text", color("color_secondary_button_text"));
  element.style.setProperty("--brand-success", b.color_success);
  element.style.setProperty("--brand-warning", b.color_warning);
  element.style.setProperty("--brand-danger", b.color_danger);
  element.style.setProperty("--brand-info", b.color_info);
  element.style.setProperty("--brand-focus", b.color_focus);
  element.style.setProperty("--brand-radius", radius);
  element.style.setProperty("--brand-shadow", shadow);
  element.style.setProperty("--brand-anim-duration", animOn ? "200ms" : "0ms");
  element.style.setProperty("--brand-text", color("color_text"));
  element.style.setProperty("--brand-heading", color("color_heading"));
  element.style.setProperty("--brand-muted", color("color_muted"));
  element.style.setProperty("--brand-card", color("color_card"));
  element.style.setProperty("--brand-sidebar-text", b.color_sidebar_text);
  element.style.setProperty("--brand-sidebar-active", b.color_sidebar_active);
  element.style.setProperty("--brand-sidebar-active-text", b.color_sidebar_active_text);
  element.style.setProperty("--brand-header", color("color_header"));
  element.style.setProperty("--brand-link", b.color_link);
  element.style.setProperty("--brand-input-background", color("color_input_background"));
  element.style.setProperty("--brand-input-text", color("color_input_text"));
  element.style.setProperty("--brand-input-border", color("color_input_border"));
  element.style.setProperty("--brand-table-header", color("color_table_header"));
  element.style.setProperty("--brand-table-header-text", color("color_table_header_text"));
  element.style.setProperty("--brand-table-row", color("color_table_row"));
  element.style.setProperty("--brand-border", color("color_border"));
  element.style.setProperty("--brand-font-scale", String(b.font_scale || 1));

  element.setAttribute("data-theme", effectiveTheme);
  element.setAttribute("data-animations", animOn && !isTruthy(b.reduced_motion) ? "true" : "false");
  element.setAttribute("data-anim-page", isTruthy(b.anim_page_transitions) ? "true" : "false");
  element.setAttribute("data-anim-modals", isTruthy(b.anim_modals) ? "true" : "false");
  element.setAttribute("data-anim-loading", isTruthy(b.anim_loading) ? "true" : "false");
  element.setAttribute("data-button-style", b.button_style || "rounded");
  element.setAttribute("data-emoji-enabled", isTruthy(b.emoji_enabled) ? "true" : "false");
}

export function applyThemeToDocument(themeMode, branding) {
  const effective = resolveEffectiveTheme(themeMode);
  applyBrandingToElement(branding, document.documentElement, effective);
}

export function applyBrandingToDocument(branding, themeMode = "light") {
  applyThemeToDocument(themeMode, branding);
  const b = mergeBranding(branding);

  document.title = b.app_name || "ERP";

  const desc = document.querySelector('meta[name="description"]');
  if (desc) desc.setAttribute("content", `${b.app_name} — ${b.tagline}`);

  const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]');
  if (appleTitle) appleTitle.setAttribute("content", b.app_name);

  const faviconHref = resolveAssetUrl(b.favicon) || "/favicon.svg";
  let link = document.querySelector('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.href = faviconHref;
}

export function getNavEmoji(branding, iconKey) {
  const b = mergeBranding(branding);
  if (!isTruthy(b.emoji_enabled)) return "";
  return b[`emoji_${iconKey}`] || "";
}

export { resolveAssetUrl };
