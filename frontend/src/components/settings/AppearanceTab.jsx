import { useEffect, useRef, useState } from "react";
import { api, uploadUrl } from "../../api/client";
import {
  CLOCK_FORMAT_OPTIONS,
  COLOR_FIELDS,
  EMOJI_NAV_KEYS,
  THEME_OPTIONS,
  isTruthy,
  mergeBranding,
} from "../../constants/brandingDefaults";
import { useBranding } from "../../context/BrandingContext";
import { useLocale } from "../../context/LocaleContext";
import { LANGUAGE_OPTIONS } from "../../i18n/translations";
import { applyBrandingToElement } from "../../utils/applyBranding";
import Toast from "../ui/Toast";

const LOGO_FIELDS = [
  { key: "logo_main", label: "Asosiy logo" },
  { key: "logo_login", label: "Login logo" },
  { key: "logo_sidebar", label: "Sidebar logo" },
  { key: "favicon", label: "Favicon" },
];

function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-3 rounded-xl bg-gray-50 px-4 py-3">
      <input type="checkbox" checked={checked} onChange={onChange} className="h-5 w-5 rounded" />
      <span className="text-sm">{label}</span>
    </label>
  );
}

function BrandingPreview({ draft, assetUrl }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) applyBrandingToElement(draft, ref.current);
  }, [draft]);

  const loginLogo = draft.logo_login || draft.logo_main;
  const sidebarLogo = draft.logo_sidebar || draft.logo_main;

  return (
    <div
      ref={ref}
      className="overflow-hidden rounded-2xl border bg-[var(--brand-background)] shadow-lg"
    >
      <p className="border-b bg-white px-4 py-2 text-xs font-bold uppercase text-gray-500">
        Jonli ko&apos;rinish
      </p>
      <div className="grid gap-4 p-4 md:grid-cols-2">
        <div className="rounded-[var(--brand-radius)] bg-white p-4 shadow-[var(--brand-shadow)]">
          <p className="mb-2 text-xs text-gray-400">Login</p>
          {loginLogo ? (
            <img
              src={assetUrl(loginLogo)}
              alt=""
              className="mx-auto mb-2 h-10 object-contain"
            />
          ) : null}
          <h3 className="text-center text-lg font-black">{draft.app_name}</h3>
          <p className="text-center text-xs text-gray-500">{draft.tagline}</p>
          <button
            type="button"
            className="brand-btn mt-4 w-full py-2 text-sm font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Kirish
          </button>
        </div>
        <div
          className="rounded-[var(--brand-radius)] p-4 text-white"
          style={{ backgroundColor: "var(--brand-sidebar)" }}
        >
          <p className="mb-2 text-xs opacity-70">Sidebar</p>
          {sidebarLogo ? (
            <img src={assetUrl(sidebarLogo)} alt="" className="mb-2 h-8 object-contain" />
          ) : (
            <h3 className="mb-3 text-lg font-black">{draft.app_name}</h3>
          )}
          <div className="space-y-1 text-sm">
            {isTruthy(draft.emoji_enabled) && (
              <>
                <p>
                  {draft.emoji_orders} Zakazlar
                </p>
                <p>
                  {draft.emoji_tasks} Vazifalar
                </p>
              </>
            )}
          </div>
          <div className="mt-4 flex gap-2">
            <span
              className="rounded px-2 py-1 text-xs text-white"
              style={{ backgroundColor: "var(--brand-success)" }}
            >
              OK
            </span>
            <span
              className="rounded px-2 py-1 text-xs text-white"
              style={{ backgroundColor: "var(--brand-warning)" }}
            >
              !
            </span>
            <span
              className="rounded px-2 py-1 text-xs text-white"
              style={{ backgroundColor: "var(--brand-danger)" }}
            >
              X
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AppearanceTab() {
  const { branding, save, reset, assetUrl, updateLocal } = useBranding();
  const { setLanguage, setTheme, setClockFormat, applySystemDefaults, t } = useLocale();
  const [draft, setDraft] = useState(mergeBranding(branding));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    setDraft(mergeBranding(branding));
    setLoading(false);
  }, [branding]);

  const patch = (key, value) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "theme_mode") {
        setTheme(value);
        updateLocal(next);
      }
      if (key === "language") {
        setLanguage(value);
      }
      if (key === "clock_format") {
        setClockFormat(value);
      }
      return next;
    });
  };

  const uploadLogo = async (key, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await api.uploadBrandingAsset(file);
      patch(key, res.url);
      setToast("Logo yuklandi");
    } catch (err) {
      setToast(err.message);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await save(draft);
      applySystemDefaults(draft);
      setToast(t("notifications.saved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm(t("common.reset") + "?")) return;
    setSaving(true);
    try {
      const data = await reset();
      const merged = mergeBranding(data);
      setDraft(merged);
      applySystemDefaults(merged);
      setToast(t("notifications.saved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  const previewDraft = draft;

  if (loading) return <p>Yuklanmoqda...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-black">{t("appearance.title")}</h2>
        <p className="text-sm text-gray-500">
          {t("appearance.systemDefaults")} — {t("notifications.themeChanged")}
        </p>
        <p className="mt-2 text-sm text-[var(--brand-muted)]">
          {t("controlCenter.appearanceMovedHint")}
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">{t("appearance.systemDefaults")}</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm text-gray-600">{t("appearance.theme")}</label>
                <select
                  value={draft.theme_mode}
                  onChange={(e) => patch("theme_mode", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                >
                  {THEME_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">{t("appearance.language")}</label>
                <select
                  value={draft.language}
                  onChange={(e) => patch("language", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">{t("appearance.clockFormat")}</label>
                <select
                  value={draft.clock_format}
                  onChange={(e) => patch("clock_format", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                >
                  {CLOCK_FORMAT_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">1. Dastur nomi</h3>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm text-gray-600">ERP nomi</label>
                <input
                  value={draft.app_name}
                  onChange={(e) => patch("app_name", e.target.value)}
                  placeholder="Velcore ERP"
                  className="w-full rounded-xl border px-4 py-3"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-600">Tagline</label>
                <input
                  value={draft.tagline}
                  onChange={(e) => patch("tagline", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                />
              </div>
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">2. Logo yuklash</h3>
            <p className="mb-4 text-xs text-gray-400">Fayllar: uploads/branding</p>
            <div className="grid gap-4 sm:grid-cols-2">
              {LOGO_FIELDS.map(({ key, label }) => (
                <div key={key} className="rounded-xl border p-4">
                  <p className="mb-2 text-sm font-medium">{label}</p>
                  {draft[key] && (
                    <img
                      src={assetUrl(draft[key]) || uploadUrl(draft[key])}
                      alt=""
                      className="mb-2 h-12 object-contain"
                    />
                  )}
                  <input
                    type="file"
                    accept="image/*,.svg,.ico"
                    onChange={(e) => uploadLogo(key, e)}
                    className="text-xs"
                  />
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">3. Mavzu ranglari</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {COLOR_FIELDS.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-3">
                  <input
                    type="color"
                    value={draft[key]}
                    onChange={(e) => patch(key, e.target.value)}
                    className="h-10 w-14 cursor-pointer rounded border"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm">{label}</p>
                    <input
                      value={draft[key]}
                      onChange={(e) => patch(key, e.target.value)}
                      className="w-full rounded border px-2 py-1 font-mono text-xs"
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">4. Tugmalar</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm">Border radius (px)</label>
                <input
                  type="number"
                  min="0"
                  max="40"
                  value={draft.button_radius}
                  onChange={(e) => patch("button_radius", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm">Usul</label>
                <select
                  value={draft.button_style}
                  onChange={(e) => patch("button_style", e.target.value)}
                  className="w-full rounded-xl border px-4 py-3"
                >
                  <option value="rounded">Yumaloq</option>
                  <option value="square">Kvadrat</option>
                </select>
              </div>
            </div>
            <div className="mt-3">
              <Toggle
                label="Soya yoqilgan"
                checked={isTruthy(draft.button_shadow)}
                onChange={(e) => patch("button_shadow", e.target.checked ? "true" : "false")}
              />
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">5. Animatsiyalar</h3>
            <div className="grid gap-2 sm:grid-cols-2">
              <Toggle
                label="Animatsiyalar yoqilgan"
                checked={isTruthy(draft.animations_enabled)}
                onChange={(e) =>
                  patch("animations_enabled", e.target.checked ? "true" : "false")
                }
              />
              <Toggle
                label="Sahifa o'tishlari"
                checked={isTruthy(draft.anim_page_transitions)}
                onChange={(e) =>
                  patch("anim_page_transitions", e.target.checked ? "true" : "false")
                }
              />
              <Toggle
                label="Modal animatsiyalari"
                checked={isTruthy(draft.anim_modals)}
                onChange={(e) => patch("anim_modals", e.target.checked ? "true" : "false")}
              />
              <Toggle
                label="Yuklanish animatsiyasi"
                checked={isTruthy(draft.anim_loading)}
                onChange={(e) => patch("anim_loading", e.target.checked ? "true" : "false")}
              />
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-6">
            <h3 className="mb-4 font-bold">6. Emoji</h3>
            <Toggle
              label="UI da emoji ko'rsatish"
              checked={isTruthy(draft.emoji_enabled)}
              onChange={(e) => patch("emoji_enabled", e.target.checked ? "true" : "false")}
            />
            {isTruthy(draft.emoji_enabled) && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {EMOJI_NAV_KEYS.map(({ key, label }) => (
                  <div key={key}>
                    <label className="mb-1 block text-xs text-gray-500">{label}</label>
                    <input
                      value={draft[key]}
                      onChange={(e) => patch(key, e.target.value)}
                      maxLength={4}
                      className="w-full rounded-xl border px-3 py-2 text-xl"
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="brand-btn flex-1 py-3 font-bold text-white disabled:opacity-50"
              style={{ backgroundColor: "var(--brand-button, #000)" }}
            >
              {saving ? t("common.saving") : t("common.save")}
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={saving}
              className="flex-1 rounded-2xl border-2 border-gray-300 py-3 font-bold"
            >
              {t("common.reset")}
            </button>
          </div>
        </div>

        <div className="xl:sticky xl:top-4 xl:self-start">
          <BrandingPreview draft={previewDraft} assetUrl={assetUrl} />
          <p className="mt-2 text-xs text-gray-400">
            Android ilova nomi native qismida qayta build talab qiladi. Web va
            Capacitor sarlavhasi avtomatik yangilanadi.
          </p>
        </div>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
