import { Link } from "react-router-dom";
import { useLocale } from "../../context/LocaleContext";

const SECTIONS = [
  { id: "menuVisibility", icon: "📋", titleKey: "controlCenter.menuTitle", descKey: "controlCenter.menuSubtitle" },
  { id: "dashboardWidgets", icon: "📊", titleKey: "controlCenter.widgetsTitle", descKey: "controlCenter.widgetsSubtitle" },
  { id: "productionStages", icon: "🏭", titleKey: "controlCenter.stagesTitle", descKey: "controlCenter.stagesSubtitle" },
  { id: "systemLogs", icon: "📜", titleKey: "controlCenter.logsTitle", descKey: "controlCenter.logsSubtitle" },
  { id: "mobileApp", icon: "📱", titleKey: "controlCenter.mobileTitle", descKey: "controlCenter.mobileSubtitle" },
];

export default function SuperAdminHubTab({ onNavigate }) {
  const { t } = useLocale();

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("controlCenter.superAdminTitle")}</h2>
      <p className="mb-6 text-sm text-[var(--brand-muted)]">{t("controlCenter.superAdminSubtitle")}</p>

      <Link
        to="/super-admin"
        className="mb-6 flex items-center gap-4 rounded-2xl border-2 border-[var(--brand-primary)] bg-[var(--brand-secondary)] p-5 transition hover:shadow-md"
      >
        <span className="text-4xl">🎛️</span>
        <div>
          <h3 className="text-lg font-black">Professional Super Admin CMS</h3>
          <p className="text-sm text-[var(--brand-muted)]">
            Menyu, modullar, theme, form/table builder, rollar, audit, rollback
          </p>
        </div>
      </Link>

      <div className="grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onNavigate?.(s.id)}
            className="rounded-2xl border bg-white p-5 text-left transition hover:border-[var(--brand-primary)]"
          >
            <span className="text-3xl">{s.icon}</span>
            <h3 className="mt-3 font-bold">{t(s.titleKey)}</h3>
            <p className="mt-1 text-sm text-[var(--brand-muted)]">{t(s.descKey)}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
