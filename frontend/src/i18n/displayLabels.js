const ACTIONS = ["read_confirm", "download", "upload", "configure", "security", "backup", "audit", "roles", "manage", "delete", "design", "edit", "view"];

export function localizedModuleLabel(t, moduleKey, fallback = moduleKey) {
  if (moduleKey === "settings") {
    const platform = t("moduleNames.platform_administration");
    return platform.startsWith("moduleNames.") ? fallback : platform;
  }
  const value = t(`moduleNames.${moduleKey || "general"}`);
  return value.startsWith("moduleNames.") ? fallback : value;
}

export function localizedPermissionLabel(t, permissionKey, fallback = permissionKey) {
  const exact = t(`permissionLabels.${permissionKey}`);
  if (!exact.startsWith("permissionLabels.")) return exact;
  const action = ACTIONS.find((candidate) => permissionKey === candidate || permissionKey.endsWith(`_${candidate}`));
  if (!action) return fallback;
  const moduleKey = permissionKey.slice(0, -(action.length + 1)) || "general";
  const moduleLabel = localizedModuleLabel(t, moduleKey, moduleKey);
  const actionLabel = t(`permissionActions.${action}`);
  return actionLabel.startsWith("permissionActions.") ? fallback : `${moduleLabel} — ${actionLabel}`;
}

export function localizedCanonical(t, domain, value) {
  if (!value) return value;
  const normalized = String(value).replaceAll(" ", "_").toLowerCase();
  const translated = t(`${domain}.${normalized}`);
  return translated.startsWith(`${domain}.`) ? value : translated;
}
