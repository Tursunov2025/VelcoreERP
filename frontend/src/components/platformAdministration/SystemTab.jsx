import { useCallback } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";
import {
  AdminCard,
  AdminSection,
  ResourceState,
  usePlatformResource,
} from "./AdminSection";
export default function SystemTab() {
  const { t, formatDate } = useLocale();
  const loader = useCallback(() => api.platformSystem(), []);
  const state = usePlatformResource(loader);
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  const rows = [
    [t("platformAdministration.version"), state.data.application_version], [t("platformAdministration.environment"), localizedCanonical(t, "canonicalStates", state.data.environment)],
    [
      t("platformAdministration.database"), `${state.data.database.engine} · ${t(state.data.database.connected ? "platformAdministration.connected" : "platformAdministration.unavailableState")}`,
    ],
    [t("platformAdministration.schema"), localizedCanonical(t, "canonicalStates", state.data.schema.status)],
    [
      t("platformAdministration.latestBackup"),
      state.data.backup.latest_at
        ? formatDate(state.data.backup.latest_at, { dateStyle: "short", timeStyle: "short" }) : t("platformAdministration.none"),
    ],
    [t("platformAdministration.backend"), localizedCanonical(t, "canonicalStates", state.data.backend.status)], [t("platformAdministration.frontendBuild"), localizedCanonical(t, "canonicalStates", state.data.frontend.build)],
    [
      t("platformAdministration.availableStorage"),
      state.data.storage.available_bytes == null
        ? t("platformAdministration.unavailableState")
        : `${(state.data.storage.available_bytes / 1024 / 1024 / 1024).toFixed(2)} GB`,
    ],
    [t("platformAdministration.scheduler"), localizedCanonical(t, "canonicalStates", state.data.scheduler.status)],
  ];
  return (
    <AdminSection
      title={t("platformAdministration.system")}
      description={t("platformAdministration.subtitle")}
    >
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map(([label, value]) => (
          <AdminCard key={label} title={label}>
            <p className="text-lg font-bold text-[var(--brand-text)]">
              {String(value)}
            </p>
          </AdminCard>
        ))}
      </div>
    </AdminSection>
  );
}
