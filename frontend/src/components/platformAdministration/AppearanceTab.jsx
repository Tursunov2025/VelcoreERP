import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import { COLOR_FIELDS } from "../../constants/brandingDefaults";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import { applyBrandingToElement } from "../../utils/applyBranding";
import { AdminCard, AdminSection, Notice, ResourceState, buttonClass, fieldClass, secondaryButtonClass, usePlatformResource } from "./AdminSection";

const contrastPairs = [
  ["color_button_text", "color_button"], ["color_secondary_button_text", "color_secondary_button"],
  ["color_sidebar_text", "color_sidebar"], ["color_sidebar_active_text", "color_sidebar_active"],
  ["color_heading", "color_background"], ["color_text", "color_background"],
  ["color_input_text", "color_input_background"], ["color_table_header_text", "color_table_header"],
];
const appearancePayloadKeys = ["app_name", "short_name", "login_footer", "theme_mode", "interface_density", "button_radius", "font_scale", "reduced_motion", "version", ...COLOR_FIELDS.map(({ key }) => key)];
const luminance = (hex) => {
  const values = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255).map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return .2126 * values[0] + .7152 * values[1] + .0722 * values[2];
};
const contrast = (a, b) => { const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x); return (high + .05) / (low + .05); };

function ThemePreview({ draft, t }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) applyBrandingToElement(draft, ref.current, draft.theme_mode === "dark" ? "dark" : "light"); }, [draft]);
  return <div ref={ref} className="brand-card space-y-4 rounded-[var(--brand-radius)] border p-5">
    <div className="flex overflow-hidden rounded-xl border border-[var(--brand-border)]">
      <aside className="w-36 space-y-2 bg-[var(--brand-sidebar)] p-3 text-[var(--brand-sidebar-text)]">
        <strong>{draft.short_name}</strong><div className="rounded-lg px-2 py-1">{t("appearance.previewItem")}</div>
        <div className="rounded-lg bg-[var(--brand-sidebar-active)] px-2 py-1 text-[var(--brand-sidebar-active-text)]">{t("appearance.previewActive")}</div>
      </aside>
      <div className="min-w-0 flex-1 bg-[var(--brand-background)] p-4">
        <h3>{t("appearance.previewHeading")}</h3><p className="text-[var(--brand-text)]">{t("appearance.previewBody")}</p>
        <a href="#preview" onClick={(e) => e.preventDefault()}>{t("appearance.previewLink")}</a>
      </div>
    </div>
    <div className="flex flex-wrap gap-2"><button className="brand-btn brand-btn-primary px-3 py-2">{t("appearance.primaryButton")}</button><button className="brand-btn brand-btn-secondary px-3 py-2">{t("appearance.secondaryButton")}</button><button disabled className="brand-btn brand-btn-primary px-3 py-2 opacity-40">{t("appearance.disabledButton")}</button></div>
    <input className="w-full rounded-xl border px-3 py-2" placeholder={t("appearance.inputPreview")} />
    <table className="w-full text-sm"><thead><tr><th className="p-2 text-left">{t("appearance.tableHeader")}</th></tr></thead><tbody><tr><td className="border-t border-[var(--brand-border)] p-2">{t("appearance.tableRow")}</td></tr></tbody></table>
    <div className="flex gap-2"><span className="rounded-lg bg-[var(--brand-success)] px-2 py-1 text-white">✓ {t("common.success")}</span><span className="rounded-lg bg-[var(--brand-warning)] px-2 py-1 text-black">! {t("common.warning")}</span><span className="rounded-lg bg-[var(--brand-danger)] px-2 py-1 text-white">! {t("common.error")}</span></div>
  </div>;
}

export default function AppearanceTab() {
  const { t } = useLocale();
  const { reload: reloadBranding } = useBranding();
  const state = usePlatformResource(useCallback(() => api.platformAppearance(), []));
  const [draft, setDraft] = useState(null); const [saved, setSaved] = useState(null); const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  useEffect(() => { if (state.data) { setDraft(state.data); setSaved(state.data); } }, [state.data]);
  const failures = useMemo(() => !draft ? [] : contrastPairs.map(([fg, bg]) => ({ fg, bg, ratio: contrast(draft[fg], draft[bg]) })).filter((x) => x.ratio < 4.5), [draft]);
  const dirty = draft && saved && JSON.stringify(draft) !== JSON.stringify(saved);
  useEffect(() => { const warn = (event) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } }; addEventListener("beforeunload", warn); return () => removeEventListener("beforeunload", warn); }, [dirty]);
  if (state.loading || state.error || !draft) return <ResourceState {...state} onRetry={state.reload} />;
  const set = (key, value) => setDraft((old) => ({ ...old, [key]: value }));
  const save = async () => { setBusy(true); setMessage(""); try { const payload = Object.fromEntries(appearancePayloadKeys.map((key) => [key, draft[key]])); const result = await api.platformSaveAppearance(payload); setDraft(result); setSaved(result); await reloadBranding(); setMessage(t("appearance.saved")); } catch (error) { if (error?.status === 409 || /409|conflict/i.test(error.message)) setMessage(t("appearance.conflict")); else setMessage(t("appearance.saveFailed")); } finally { setBusy(false); } };
  const restore = async () => { if (!confirm(t("appearance.restoreConfirm"))) return; setBusy(true); try { const result = await api.platformResetAppearance(); setDraft(result); setSaved(result); await reloadBranding(); setMessage(t("appearance.restored")); } finally { setBusy(false); } };
  return <AdminSection title={t("platformAdministration.appearance")} description={t("appearance.organizationScope")} actions={<><button className={secondaryButtonClass} disabled={!dirty || busy} onClick={() => setDraft(saved)}>{t("common.cancel")}</button><button className={secondaryButtonClass} disabled={busy} onClick={restore}>{t("appearance.restoreDefaults")}</button><button className={buttonClass} disabled={busy || !dirty || failures.length > 0} onClick={save}>{busy ? t("common.saving") : t("common.save")}</button></>}>
    {message && <Notice tone={message === t("appearance.saveFailed") || message === t("appearance.conflict") ? "error" : "success"}>{message}</Notice>}
    {failures.length > 0 && <Notice tone="error"><strong>{t("appearance.contrastBlocked")}</strong><ul className="mt-2 list-disc pl-5">{failures.map((item) => <li key={`${item.fg}-${item.bg}`}>{t(`appearance.colors.${item.fg}`)} / {t(`appearance.colors.${item.bg}`)}: {item.ratio.toFixed(2)}:1 — {t("appearance.suggestedText", { color: contrast("#000000", draft[item.bg]) >= 4.5 ? "#000000" : "#ffffff" })}</li>)}</ul></Notice>}
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]"><div className="space-y-5">
      <AdminCard title={t("appearance.identity")}><div className="grid gap-4 sm:grid-cols-2">{[["app_name","appearance.appName"],["short_name","appearance.shortName"],["login_footer","appearance.loginFooter"]].map(([key,label]) => <label key={key}><span className="mb-1 block text-sm font-bold">{t(label)}</span><input className={fieldClass} value={draft[key] || ""} onChange={(e) => set(key,e.target.value)} /></label>)}</div></AdminCard>
      <AdminCard title={t("appearance.designTokens")} description={t("appearance.designTokensDescription")}><div className="grid gap-3 sm:grid-cols-2">{COLOR_FIELDS.map(({key,labelKey}) => <label key={key} className="flex items-center gap-3"><input type="color" value={draft[key]} onChange={(e)=>set(key,e.target.value)} className="h-11 w-14 rounded border"/><span className="min-w-0 flex-1 text-sm"><b className="block">{t(labelKey)}</b><input aria-label={t(labelKey)} className={`${fieldClass} mt-1 font-mono`} value={draft[key]} onChange={(e)=>set(key,e.target.value)} /></span></label>)}</div></AdminCard>
      <AdminCard title={t("appearance.behavior")}><div className="grid gap-4 sm:grid-cols-2"><label>{t("appearance.organizationTheme")}<select className={fieldClass} value={draft.theme_mode} onChange={(e)=>set("theme_mode",e.target.value)}><option value="light">{t("appearance.themeLight")}</option><option value="dark">{t("appearance.themeDark")}</option><option value="system">{t("appearance.themeAuto")}</option></select></label><label>{t("appearance.density")}<select className={fieldClass} value={draft.interface_density} onChange={(e)=>set("interface_density",e.target.value)}><option value="comfortable">{t("appearance.comfortable")}</option><option value="compact">{t("appearance.compact")}</option></select></label><label>{t("appearance.radius")}<input type="number" min="0" max="40" className={fieldClass} value={draft.button_radius} onChange={(e)=>set("button_radius",Number(e.target.value))}/></label><label>{t("appearance.fontScale")}<input type="number" min="0.875" max="1.25" step="0.025" className={fieldClass} value={draft.font_scale} onChange={(e)=>set("font_scale",Number(e.target.value))}/></label><label className="flex items-center gap-2"><input type="checkbox" checked={Boolean(draft.reduced_motion)} onChange={(e)=>set("reduced_motion",e.target.checked)}/>{t("appearance.reducedMotion")}</label></div></AdminCard>
    </div><div className="2xl:sticky 2xl:top-4 2xl:self-start"><AdminCard title={t("appearance.livePreview")} description={t("appearance.draftOnly")}><ThemePreview draft={draft} t={t}/></AdminCard></div></div>
  </AdminSection>;
}
