import { useCallback, useState } from "react";
import { api, getStoredTokens } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";
import {
  AdminCard,
  AdminSection,
  Notice,
  ResourceState,
  buttonClass,
  secondaryButtonClass,
  usePlatformResource,
} from "./AdminSection";
export default function BackupTab() {
  const { t, formatDate } = useLocale();
  const loader = useCallback(() => api.platformBackups(), []);
  const state = usePlatformResource(loader);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const result = await api.platformCreateBackup();
      setMessage(t("platformAdministration.backupCreated", { name: result.name }));
      await state.reload();
    } catch (error) {
      state.setError(error.message);
    } finally {
      setBusy(false);
    }
  };
  const download = async (name) => {
    const response = await fetch(api.platformBackupDownloadUrl(name), {
      headers: {
        Authorization: `Bearer ${getStoredTokens()?.access_token || ""}`,
      },
    });
    if (!response.ok) throw new Error(t("errors.network"));
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.backup")}
      description={t("platformAdministration.subtitle")}
      actions={
        <button disabled={busy} className={buttonClass} onClick={create}>
          {t("platformAdministration.createBackup")}
        </button>
      }
    >
      {message ? <Notice>{message}</Notice> : null}
      <AdminCard title={t("platformAdministration.databaseStatus")}>
        <p className="text-sm">
          {t("platformAdministration.engine")}: <strong>{state.data.database.engine}</strong> · {t("common.status")}: <strong>{localizedCanonical(t, "canonicalStates", state.data.database.status)}</strong> · {t("platformAdministration.restore")}: <strong>{t("platformAdministration.offlineOnly")}</strong>
        </p>
      </AdminCard>
      <AdminCard title={t("platformAdministration.availableBackups")}>
        <div className="overflow-x-auto">
          <table className="min-w-[900px] w-full text-left text-sm">
            <thead>
              <tr>
                {[
                  t("platformAdministration.created"), t("platformAdministration.name"), t("platformAdministration.size"), t("platformAdministration.validation"),
                  "SHA-256",
                  t("common.actions"),
                ].map((label) => (
                  <th className="border-b p-3" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.data.items.map((item) => (
                <tr key={item.name}>
                  <td className="border-b p-3">
                    {formatDate(item.created_at, { dateStyle: "short", timeStyle: "short" })}
                  </td>
                  <td className="border-b p-3 font-mono">{item.name}</td>
                  <td className="border-b p-3">
                    {(item.size / 1024 / 1024).toFixed(2)} MB
                  </td>
                  <td className="border-b p-3">
                    {t(item.valid ? "platformAdministration.valid" : "platformAdministration.invalid")}
                  </td>
                  <td
                    className="max-w-52 truncate border-b p-3 font-mono"
                    title={item.sha256}
                  >
                    {item.sha256}
                  </td>
                  <td className="border-b p-3">
                    <div className="flex gap-3">
                      <button
                        className="text-[var(--brand-primary)]"
                        onClick={() =>
                          download(item.name).catch((e) =>
                            state.setError(e.message),
                          )
                        }
                      >
                        {t("platformAdministration.download")}
                      </button>
                      <button
                        onClick={() =>
                          api
                            .platformBackupPreflight(item.name)
                            .then((result) =>
                              setMessage(
                                t(
                                  result.valid
                                    ? "platformAdministration.preflightValid"
                                    : "platformAdministration.preflightInvalid",
                                  { name: item.name },
                                ),
                              ),
                            )
                        }
                      >
                        {t("platformAdministration.preflight")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {state.data.items.length === 0 ? (
            <p className="p-8 text-center text-[var(--brand-muted)]">
              {t("platformAdministration.noBackups")}
            </p>
          ) : null}
        </div>
      </AdminCard>
    </AdminSection>
  );
}
