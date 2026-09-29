import { useCallback, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
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
const flatten = (items, depth = 0) =>
  items.flatMap((item) => [
    { ...item, depth },
    ...flatten(item.children || [], depth + 1),
  ]);
export default function NavigationTab() {
  const { t } = useLocale();
  const displayLabel = (item) => {
    const localized = t(`nav.${item.nav_key}`);
    return localized.startsWith("nav.") ? item.label : localized;
  };
  const loader = useCallback(() => api.platformNavigation(), []);
  const state = usePlatformResource(loader);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async (item, changes) => {
    setBusy(true);
    try {
      await api.platformSaveNavigation(item.id, {
        label: item.label,
        icon: state.data.icon_allowlist.includes(item.icon)
          ? item.icon
          : "dashboard",
        visible: item.visible,
        sort_order: item.sort_order,
        permissions: item.permissions || [],
        ...changes,
      });
      setMessage(t("notifications.saved"));
      await state.reload();
    } catch (error) {
      state.setError(error.message);
    } finally {
      setBusy(false);
    }
  };
  if (state.loading || state.error)
    return <ResourceState {...state} onRetry={state.reload} />;
  return (
    <AdminSection
      title={t("platformAdministration.navigation")}
      description={t("platformAdministration.subtitle")}
      actions={
        <button
          className={secondaryButtonClass}
          onClick={() =>
            window.confirm(t("dialogs.restoreDefaults")) &&
            api.platformResetNavigation().then(state.reload)
          }
        >
          {t("platformAdministration.restoreDefaults")}
        </button>
      }
    >
      {message ? <Notice>{message}</Notice> : null}
      <AdminCard
        title={t("platformAdministration.navigationTree")}
        description={t("platformAdministration.subtitle")}
      >
        <div className="space-y-2">
          {flatten(state.data.items).map((item) => (
            <div
              key={item.id}
              className="grid gap-3 rounded-2xl border border-[var(--brand-muted)]/20 p-3 md:grid-cols-[minmax(160px,1fr)_140px_80px_minmax(180px,1fr)_100px] md:items-center"
              style={{ marginLeft: `${Math.min(item.depth, 3) * 16}px` }}
            >
              <label>
                <span className="sr-only">{t("platformAdministration.label")}</span>
                <input
                  className={fieldClass}
                  defaultValue={displayLabel(item)}
                  onBlur={(e) =>
                    e.target.value !== displayLabel(item) &&
                    save(item, { label: e.target.value })
                  }
                />
              </label>
              <select
                aria-label={t("platformAdministration.icon")}
                className={fieldClass}
                value={
                  state.data.icon_allowlist.includes(item.icon)
                    ? item.icon
                    : "dashboard"
                }
                onChange={(e) => save(item, { icon: e.target.value })}
              >
                {state.data.icon_allowlist.map((icon) => (
                  <option key={icon}>{icon}</option>
                ))}
              </select>
              <input
                aria-label={t("platformAdministration.order")}
                className={fieldClass}
                type="number"
                min="0"
                value={item.sort_order}
                onChange={(e) =>
                  save(item, { sort_order: Number(e.target.value) })
                }
              />
              <input
                aria-label={t("platformAdministration.visibilityPermissions")}
                className={fieldClass}
                defaultValue={(item.permissions || []).join(", ")}
                onBlur={(e) =>
                  save(item, {
                    permissions: e.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean),
                  })
                }
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={item.visible && !item.hidden}
                  disabled={busy}
                  onChange={(e) => save(item, { visible: e.target.checked })}
                />{" "}
                {t("platformAdministration.visible")}
              </label>
            </div>
          ))}
        </div>
      </AdminCard>
    </AdminSection>
  );
}
