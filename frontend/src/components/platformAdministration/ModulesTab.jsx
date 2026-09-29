import { useCallback, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import { localizedModuleLabel } from "../../i18n/displayLabels";
import {
  AdminCard,
  AdminSection,
  Notice,
  ResourceState,
  fieldClass,
  usePlatformResource,
} from "./AdminSection";
export default function ModulesTab() {
  const { t } = useLocale();
  const loader = useCallback(() => api.platformModules(), []);
  const state = usePlatformResource(loader);
  const [message, setMessage] = useState("");
  const save = async (module, next) => {
    if (
      !window.confirm(
        `${t("platformAdministration.modules")}: ${module.label} — ${t(`statuses.${next}`)}?`,
      )
    )
      return;
    try {
      await api.platformSaveModule(module.module_key, {
        state: next,
        version: state.data.version,
      });
      setMessage(t("notifications.saved"));
      await state.reload();
    } catch (error) {
      state.setError(error.message);
    }
  };
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.modules")}
      description={t("platformAdministration.subtitle")}
    >
      {message ? <Notice>{message}</Notice> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {state.data.items.map((module) => (
          <AdminCard
            key={module.module_key}
            title={localizedModuleLabel(t, module.module_key, module.label)}
            description={module.routes.join(" · ")}
          >
            <div className="flex items-center justify-between gap-4">
              <div className="text-sm text-[var(--brand-muted)]">
                {t("platformAdministration.dependencies")}: {module.dependencies.join(", ") || t("platformAdministration.none")}
                {module.required ? (
                  <strong className="ml-2 text-[var(--brand-text)]">
                    {t("platformAdministration.coreModule")}
                  </strong>
                ) : null}
              </div>
              <select
                aria-label={`${module.label} state`}
                className={`${fieldClass} max-w-44`}
                value={module.state}
                disabled={module.required}
                onChange={(e) => save(module, e.target.value)}
              >
                <option value="enabled">{t("common.enabled")}</option>
                <option value="maintenance">{t("platformAdministration.maintenance")}</option>
                <option value="disabled">{t("common.disabled")}</option>
              </select>
            </div>
          </AdminCard>
        ))}
      </div>
    </AdminSection>
  );
}
