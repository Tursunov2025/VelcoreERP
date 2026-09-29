import { useCallback } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import {
  AdminCard,
  AdminSection,
  ResourceState,
  usePlatformResource,
} from "./AdminSection";
export default function AboutTab() {
  const { t } = useLocale();
  const loader = useCallback(() => api.platformAbout(), []);
  const state = usePlatformResource(loader);
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.about")}
      description={t("platformAdministration.subtitle")}
    >
      <AdminCard title={state.data.product_name}>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[var(--brand-muted)]">{t("platformAdministration.version")}</dt>
            <dd className="font-bold">{state.data.version}</dd>
          </div>
          <div>
            <dt className="text-[var(--brand-muted)]">{t("platformAdministration.build")}</dt>
            <dd className="font-bold">{state.data.build}</dd>
          </div>
          <div>
            <dt className="text-[var(--brand-muted)]">{t("platformAdministration.databaseSchema")}</dt>
            <dd className="font-bold">
              {state.data.schema.table_count} {t("platformAdministration.tables")}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--brand-muted)]">{t("platformAdministration.license")}</dt>
            <dd className="font-bold">
              {state.data.license ||
                state.data.copyright ||
                t("platformAdministration.notConfigured")}
            </dd>
          </div>
        </dl>
        <p className="mt-6 rounded-2xl border p-4 text-sm text-[var(--brand-muted)]">
          {t("aboutNotice")}
        </p>
        {state.data.links.length ? (
          <ul className="mt-4">
            {state.data.links.map((link) => (
              <li key={link.url}>
                <a href={link.url} rel="noreferrer" target="_blank">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        ) : null}
      </AdminCard>
    </AdminSection>
  );
}
