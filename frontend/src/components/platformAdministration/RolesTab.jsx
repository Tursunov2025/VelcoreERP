import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import { localizedModuleLabel, localizedPermissionLabel } from "../../i18n/displayLabels";
import {
  AdminCard,
  AdminSection,
  Notice,
  ResourceState,
  buttonClass,
  fieldClass,
  secondaryButtonClass,
  usePlatformResource,
} from "./AdminSection";

export default function RolesTab() {
  const { t } = useLocale();
  const roleLabel = (role) => { const system = t(`systemRoleNames.${role.role_key}`); if (!system.startsWith("systemRoleNames.")) return system; const value = t(`roleNames.${role.role_key}`); return value.startsWith("roleNames.") ? role.label : value; };
  const roleDescription = (role) => {
    const translated = t(`systemRoleDescriptions.${role.role_key}`);
    return translated.startsWith("systemRoleDescriptions.")
      ? role.description || role.role_key
      : translated;
  };
  const loader = useCallback(() => api.platformRoles(), []);
  const state = usePlatformResource(loader);
  const [selectedId, setSelectedId] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const selected =
    state.data?.roles.find((role) => role.id === selectedId) ||
    state.data?.roles[0];
  const [draftPermissions, setDraftPermissions] = useState({});
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    setDraftPermissions(selected?.permissions || {});
    setDirty(false);
  }, [selected?.id, state.data]);
  const groups = useMemo(
    () =>
      (state.data?.permission_groups || []).reduce(
        (result, permission) => ({
          ...result,
          [permission.module || "general"]: [
            ...(result[permission.module || "general"] || []),
            permission,
          ],
        }),
        {},
      ),
    [state.data],
  );
  const mutate = async (operation) => {
    setBusy(true);
    setMessage("");
    try {
      await operation();
      setMessage(t("notifications.saved"));
      await state.reload();
    } catch (error) {
      state.setError(error.message);
    } finally {
      setBusy(false);
    }
  };
  const savePermissions = () =>
    selected && mutate(() => api.platformUpdateRole(selected.id, { permissions: draftPermissions }));
  const create = () => {
    const role_key = window.prompt(t("platformAdministration.roleKeyPrompt"));
    if (!role_key) return;
    const label = window.prompt(t("platformAdministration.roleLabelPrompt"));
    if (!label) return;
    mutate(() => api.platformCreateRole({ role_key, label, permissions: {} }));
  };
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.roles")}
      description={t("platformAdministration.subtitle")}
      actions={
        <button className={buttonClass} onClick={create}>
          {t("platformAdministration.createRole")}
        </button>
      }
    >
      {message ? <Notice>{message}</Notice> : null}
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <AdminCard title={t("platformAdministration.rolesList")}>
          <div className="space-y-2">
            {state.data.roles.map((role) => (
              <button
                key={role.id}
                onClick={() => setSelectedId(role.id)}
                className={`w-full rounded-2xl border p-3 text-left ${selected?.id === role.id ? "border-[var(--brand-primary)] bg-[var(--brand-secondary)]" : "border-[var(--brand-muted)]/20"}`}
              >
                <span className="block font-bold text-[var(--brand-text)]">
                  {roleLabel(role)}
                </span>
                <span className="text-xs text-[var(--brand-muted)]">
                  {role.user_count} {t("platformAdministration.usersCount")} · {t(role.is_active ? "common.active" : "common.inactive")}
                </span>
              </button>
            ))}
          </div>
        </AdminCard>
        {selected ? (
          <AdminCard
            title={roleLabel(selected)}
            description={roleDescription(selected)}
          >
            <div className="mb-5 flex flex-wrap gap-2">
              <button
                disabled={busy}
                className={secondaryButtonClass}
                onClick={() => {
                  const label = window.prompt(t("platformAdministration.newLabelPrompt"), selected.label);
                  if (label)
                    mutate(() =>
                      api.platformUpdateRole(selected.id, { label }),
                    );
                }}
              >
                {t("platformAdministration.rename")}
              </button>
              <button
                disabled={busy || selected.role_key === "super_admin"}
                className={secondaryButtonClass}
                onClick={() =>
                  mutate(() =>
                    api.platformUpdateRole(selected.id, {
                      is_active: !selected.is_active,
                    }),
                  )
                }
              >
                {t(selected.is_active ? "platformAdministration.deactivate" : "platformAdministration.activate")}
              </button>
              <button
                disabled={busy || selected.is_system}
                className="rounded-xl border border-red-500/40 px-4 py-2 text-sm font-bold text-red-600 disabled:opacity-40"
                onClick={() =>
                  window.confirm(t("platformAdministration.deleteConfirm", { name: selected.label })) &&
                  mutate(() => api.platformDeleteRole(selected.id))
                }
              >
                {t("common.delete")}
              </button>
              {!selected.permissions_inherited ? (
                <>
                  <button disabled={busy || !dirty} className={buttonClass} onClick={savePermissions}>
                    {busy ? t("common.saving") : t("common.save")}
                  </button>
                  <button
                    disabled={busy || !dirty}
                    className={secondaryButtonClass}
                    onClick={() => { setDraftPermissions(selected.permissions); setDirty(false); }}
                  >
                    {t("common.cancel")}
                  </button>
                </>
              ) : null}
            </div>
            {selected.permissions_inherited ? (
              <Notice>{t("platformAdministration.inheritedSystemPermissions")}</Notice>
            ) : null}
            <div className="space-y-5">
              {Object.entries(groups).map(([module, permissions]) => (
                <fieldset
                  key={module}
                  className="rounded-2xl border border-[var(--brand-muted)]/20 p-4"
                >
                  <legend className="px-2 text-sm font-black capitalize text-[var(--brand-text)]">
                    {localizedModuleLabel(t, module, module)}
                  </legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {permissions.map((permission) => (
                      <label
                        key={permission.key}
                        className="flex items-start gap-3 text-sm text-[var(--brand-text)]"
                      >
                        <input
                          type="checkbox"
                          checked={Boolean(
                            draftPermissions[permission.key],
                          )}
                          disabled={busy || selected.permissions_inherited}
                          onChange={(event) => { setDraftPermissions((old) => ({ ...old, [permission.key]: event.target.checked })); setDirty(true); }}
                        />
                        <span>
                          <strong>{localizedPermissionLabel(t, permission.key, permission.label)}</strong>
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          </AdminCard>
        ) : null}
      </div>
    </AdminSection>
  );
}
