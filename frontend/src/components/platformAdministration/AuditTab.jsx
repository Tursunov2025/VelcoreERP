import { useCallback, useState } from "react";
import { api, getStoredTokens } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";
import {
  AdminCard,
  AdminSection,
  ResourceState,
  fieldClass,
  secondaryButtonClass,
  usePlatformResource,
} from "./AdminSection";
export default function AuditTab() {
  const { t, formatDate } = useLocale();
  const [filters, setFilters] = useState({
    page: 1,
    page_size: 50,
    actor: "",
    action: "",
    module: "",
    result: "",
  });
  const loader = useCallback(() => api.platformAudit(filters), [filters]);
  const state = usePlatformResource(loader);
  const exportCsv = async () => {
    const response = await fetch(api.platformAuditCsvUrl(), {
      headers: {
        Authorization: `Bearer ${getStoredTokens()?.access_token || ""}`,
      },
    });
    if (!response.ok) throw new Error(t("errors.network"));
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = "platform-audit.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  };
  return (
    <AdminSection
      title={t("platformAdministration.auditLog")}
      description={t("platformAdministration.subtitle")}
      actions={
        <button
          className={secondaryButtonClass}
          onClick={() => exportCsv().catch((e) => state.setError(e.message))}
        >
          {t("platformAdministration.exportCsv")}
        </button>
      }
    >
      <AdminCard title={t("platformAdministration.filters")}>
        <div className="grid gap-3 md:grid-cols-4">
          {[
            [t("platformAdministration.actor"), "actor"], [t("platformAdministration.action"), "action"], [t("platformAdministration.module"), "module"], [t("platformAdministration.result"), "result"],
          ].map(([label, key]) => (
            <label key={key}>
              <span className="sr-only">{label}</span>
              <input
                className={fieldClass}
                placeholder={label}
                value={filters[key]}
                onChange={(e) =>
                  setFilters((old) => ({
                    ...old,
                    [key]: e.target.value,
                    page: 1,
                  }))
                }
              />
            </label>
          ))}
        </div>
      </AdminCard>
      <ResourceState {...state} onRetry={state.reload} />
      {state.data ? (
        <AdminCard title={`${state.data.total} ${t("platformAdministration.events")}`}>
          <div className="overflow-x-auto">
            <table className="min-w-[1200px] w-full text-left text-sm">
              <thead>
                <tr>
                  {[
                    t("platformAdministration.time"), t("platformAdministration.actor"), t("platformAdministration.action"), t("platformAdministration.module"), t("platformAdministration.entity"), t("platformAdministration.result"),
                    "IP",
                    t("platformAdministration.requestId"),
                  ].map((label) => (
                    <th className="border-b p-3" key={label}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {state.data.items.map((item) => (
                  <tr key={item.id}>
                    <td className="border-b p-3">
                      {item.timestamp
                        ? formatDate(item.timestamp, { dateStyle: "short", timeStyle: "short" })
                        : "—"}
                    </td>
                    <td className="border-b p-3">{item.actor}</td>
                    <td className="border-b p-3">{localizedCanonical(t, "auditActions", item.action)}</td>
                    <td className="border-b p-3">{item.module}</td>
                    <td className="border-b p-3">
                      {item.entity_type} {item.entity_id || ""}
                    </td>
                    <td className="border-b p-3">{localizedCanonical(t, "canonicalStates", item.result)}</td>
                    <td className="border-b p-3">{item.ip_address || "—"}</td>
                    <td className="border-b p-3 font-mono">
                      {item.correlation_id || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex justify-between text-sm">
            <button
              disabled={filters.page === 1}
              onClick={() =>
                setFilters((old) => ({ ...old, page: old.page - 1 }))
              }
            >
              {t("platformAdministration.previous")}
            </button>
            <span>{t("platformAdministration.page")} {filters.page}</span>
            <button
              disabled={filters.page * filters.page_size >= state.data.total}
              onClick={() =>
                setFilters((old) => ({ ...old, page: old.page + 1 }))
              }
            >
              {t("platformAdministration.next")}
            </button>
          </div>
        </AdminCard>
      ) : null}
    </AdminSection>
  );
}
