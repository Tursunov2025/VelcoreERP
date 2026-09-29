import { useLocation } from "react-router-dom";
import { useLocale } from "../../context/LocaleContext";
import { useUiConfig } from "../../hooks/useUiConfig";

const ROUTES = [
  ["/display-center", "display_center"],
  ["/materials", "materials"],
  ["/mes/terminal/qc", "qc"],
  ["/mes/templates", "technology"],
  ["/mes", "mes"],
  ["/logistics/llp", "llp"],
  ["/logistics/gps", "gps"],
  ["/logistics", "logistics"],
  ["/warehouse", "warehouse"],
  ["/production", "production"],
  ["/finance", "finance"],
  ["/invoices", "finance"],
  ["/orders", "orders"],
  ["/crm", "crm"],
  ["/chat", "chat"],
  ["/tasks", "tasks"],
  ["/analytics", "analytics"],
];

export default function ModuleStateGate({ children }) {
  const { t } = useLocale();
  const { pathname } = useLocation();
  const { config, loading } = useUiConfig();
  if (pathname.startsWith("/admin")) return children;
  const moduleKey = ROUTES.find(
    ([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )?.[1];
  const state = moduleKey ? config?.module_states?.[moduleKey] : "enabled";
  if (!loading && state && state !== "enabled")
    return (
      <section className="mx-auto mt-16 max-w-xl rounded-3xl border bg-[var(--brand-card)] p-8 text-center shadow-sm">
        <h1 className="text-2xl font-black">
          {t("platformAdministration.module")} — {state === "maintenance" ? t("platformAdministration.maintenance") : t("common.disabled")}
        </h1>
        <p className="mt-3 text-sm text-[var(--brand-muted)]">
          {t("platformAdministration.unavailable")}
        </p>
      </section>
    );
  return children;
}
