import { NavLink } from "react-router-dom";
import { useLocale } from "../../context/LocaleContext";

const sections = [
  ["dashboard", "/logistics"], ["shipments", "/logistics/shipments"],
  ["loading", "/logistics/loading"], ["transport", "/logistics/transport"],
  ["drivers", "/logistics/drivers"], ["gps", "/logistics/gps"],
  ["history", "/logistics/delivery-history"],
];

export default function LogisticsSectionNav() {
  const { t } = useLocale();
  return <nav aria-label={t("logisticsCenter.navigation")} className="mb-5 flex gap-2 overflow-x-auto rounded-2xl border bg-[var(--brand-card)] p-2">
    {sections.map(([key,path]) => <NavLink key={key} end={path === "/logistics"} to={path} className={({isActive}) => `whitespace-nowrap rounded-xl px-3 py-2 text-sm font-bold ${isActive ? "text-white" : "text-[var(--brand-muted)] hover:bg-black/5"}`} style={({isActive}) => isActive ? {backgroundColor:"var(--brand-button)"} : undefined}>{t(`logisticsCenter.sections.${key}`)}</NavLink>)}
  </nav>;
}
