import { getApiBase } from "../api/client";
import { isTruthy, mergeBranding } from "../constants/brandingDefaults";

const DARK_PALETTE = {
  color_primary: "#f5f5f5",
  color_secondary: "#1e293b",
  color_background: "#0f1419",
  color_sidebar: "#0a0a0a",
  color_button: "#3b82f6",
};

function resolveAssetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  const base = getApiBase().replace(/\/$/, "");
  return `${base}${url.startsWith("/") ? url : `/${url}`}`;
}

export function resolveEffectiveTheme(themeMode) {
  if (themeMode === "auto") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return themeMode === "dark" ? "dark" : "light";
}

function brandingForTheme(branding, effectiveTheme) {
  const b = mergeBranding(branding);
  if (effectiveTheme === "dark") {
    return { ...b, ...DARK_PALETTE };
  }
  return b;
}

export function applyBrandingToElement(branding, element, effectiveTheme = "light") {
  const b = brandingForTheme(branding, effectiveTheme);
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
  element.style.setProperty("--brand-background", b.color_background);
  element.style.setProperty("--brand-sidebar", b.color_sidebar);
  element.style.setProperty("--brand-button", b.color_button);
  element.style.setProperty("--brand-success", b.color_success);
  element.style.setProperty("--brand-warning", b.color_warning);
  element.style.setProperty("--brand-danger", b.color_danger);
  element.style.setProperty("--brand-radius", radius);
  element.style.setProperty("--brand-shadow", shadow);
  element.style.setProperty("--brand-anim-duration", animOn ? "200ms" : "0ms");
  element.style.setProperty("--brand-text", effectiveTheme === "dark" ? "#f5f5f5" : "#111827");
  element.style.setProperty("--brand-muted", effectiveTheme === "dark" ? "#94a3b8" : "#6b7280");
  element.style.setProperty("--brand-card", effectiveTheme === "dark" ? "#1e293b" : "#ffffff");

  element.setAttribute("data-theme", effectiveTheme);
  element.setAttribute("data-animations", animOn ? "true" : "false");
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
