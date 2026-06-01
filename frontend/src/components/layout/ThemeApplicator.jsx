import { useEffect } from "react";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import { applyThemeToDocument } from "../../utils/applyBranding";

export default function ThemeApplicator({ children }) {
  const { branding } = useBranding();
  const { theme } = useLocale();

  useEffect(() => {
    applyThemeToDocument(theme, branding);
  }, [theme, branding]);

  useEffect(() => {
    if (theme !== "auto") return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyThemeToDocument("auto", branding);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, branding]);

  return children;
}
