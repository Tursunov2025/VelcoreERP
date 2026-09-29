import { useCallback } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import {
  AdminCard,
  AdminSection,
  ResourceState,
  secondaryButtonClass,
  usePlatformResource,
} from "./AdminSection";
export default function IntegrationsTab() {
  const { t } = useLocale();
  const loader = useCallback(() => api.platformIntegrations(), []);
  const state = usePlatformResource(loader);
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.integrations")}
      description={t("platformAdministration.subtitle")}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {state.data.items.map((item) => (
          <AdminCard
            key={item.key}
            title={item.label}
            description={
              item.implemented ? t("platformAdministration.supportedIntegration") : t("platformAdministration.notImplemented")
            }
          >
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <dt className="text-[var(--brand-muted)]">{t("platformAdministration.configured")}</dt>
              <dd>{t(item.configured ? "common.yes" : "common.no")}</dd>
              <dt className="text-[var(--brand-muted)]">{t("common.enabled")}</dt>
              <dd>{t(item.enabled ? "common.yes" : "common.no")}</dd>
              <dt className="text-[var(--brand-muted)]">{t("platformAdministration.credential")}</dt>
              <dd>{item.secret || t("platformAdministration.notConfigured")}</dd>
              <dt className="text-[var(--brand-muted)]">{t("platformAdministration.lastSuccess")}</dt>
              <dd>{item.last_success || t("platformAdministration.never")}</dd>
              <dt className="text-[var(--brand-muted)]">{t("platformAdministration.lastError")}</dt>
              <dd>{item.last_error || t("platformAdministration.noneRecorded")}</dd>
            </dl>
            {!item.implemented ? (
              <p className="mt-4 rounded-xl bg-amber-500/10 p-3 text-sm text-amber-700">
                {t("platformAdministration.integrationUnavailable")}
              </p>
            ) : (
              <div className="mt-4 flex items-center gap-3">
                <button
                  className={secondaryButtonClass}
                  disabled={!item.configured}
                  onClick={() =>
                    api
                      .platformTestTelegram()
                      .then(state.reload)
                      .catch((error) => state.setError(error.message))
                  }
                >
                  {t("platformAdministration.sendTest")}
                </button>
                <span className="text-xs text-[var(--brand-muted)]">
                  {t("platformAdministration.secretsWriteOnly")}
                </span>
              </div>
            )}
          </AdminCard>
        ))}
      </div>
    </AdminSection>
  );
}
