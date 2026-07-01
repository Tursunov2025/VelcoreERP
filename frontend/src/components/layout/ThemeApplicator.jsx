import { useEffect } from "react";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import { useUiConfig } from "../../hooks/useUiConfig";
import { applyThemeToDocument } from "../../utils/applyBranding";

function applySuperAdminTheme(theme) {
  if (!theme || typeof theme !== "object") return;
  const el = document.documentElement;
  const map = {
    primary_color: "--brand-primary",
    secondary_color: "--brand-secondary",
    sidebar_color: "--brand-sidebar",
    card_color: "--brand-card",
    button_color: "--brand-button",
    background_color: "--brand-background",
    text_color: "--brand-text",
  };
  Object.entries(map).forEach(([key, cssVar]) => {
    if (theme[key]) el.style.setProperty(cssVar, theme[key]);
  });
  if (theme.font_size_base) el.style.setProperty("--brand-font-size", theme.font_size_base);
  if (theme.border_radius) el.style.setProperty("--brand-radius", theme.border_radius);
  if (theme.animations_enabled === false) {
    el.classList.add("velcore-no-animations");
  } else {
    el.classList.remove("velcore-no-animations");
  }
}

export default function ThemeApplicator({ children }) {
  const { branding } = useBranding();
  const { theme } = useLocale();
  const { config } = useUiConfig();
  const superTheme = config?.super_admin?.theme;

  useEffect(() => {
    applyThemeToDocument(theme, branding);
    applySuperAdminTheme(superTheme);
  }, [theme, branding, superTheme]);

  useEffect(() => {
    if (theme !== "auto") return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      applyThemeToDocument("auto", branding);
      applySuperAdminTheme(superTheme);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, branding, superTheme]);

  return children;
}
