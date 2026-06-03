import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { MENU_NAV_KEYS } from "../../constants/controlCenter";
import { invalidateUiConfigCache } from "../../hooks/useUiConfig";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

export default function MenuVisibilityTab() {
  const { t } = useLocale();
  const [visibility, setVisibility] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    api
      .adminGetExecutiveSettings()
      .then((data) => {
        try {
          const parsed = JSON.parse(data.nav_visibility_json || "{}");
          setVisibility(parsed);
        } catch {
          setVisibility({});
        }
      })
      .catch((e) => setToast(e.message))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (key) => {
    setVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const save = async () => {
    setSaving(true);
    setToast("");
    try {
      const merged = {};
      MENU_NAV_KEYS.forEach(({ iconKey }) => {
        merged[iconKey] = visibility[iconKey] !== false;
      });
      await api.adminUpdateExecutiveSettings({
        nav_visibility_json: JSON.stringify(merged),
      });
      invalidateUiConfigCache();
      setToast(t("controlCenter.saved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>{t("common.loading")}</p>;

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("controlCenter.menuTitle")}</h2>
      <p className="mb-4 text-sm text-[var(--brand-muted)]">{t("controlCenter.menuSubtitle")}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {MENU_NAV_KEYS.map(({ iconKey, path, labelKey }) => (
          <label
            key={iconKey}
            className="flex min-h-[48px] cursor-pointer items-center justify-between rounded-xl border bg-white px-4 py-3"
          >
            <span className="text-sm font-semibold">
              {t(labelKey)} <span className="text-xs text-gray-400">{path}</span>
            </span>
            <input
              type="checkbox"
              checked={visibility[iconKey] !== false}
              onChange={() => toggle(iconKey)}
              className="h-5 w-5"
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        disabled={saving}
        onClick={save}
        className="brand-btn mt-6 rounded-xl px-6 py-3 font-bold text-white disabled:opacity-60"
        style={{ backgroundColor: "var(--brand-button)" }}
      >
        {saving ? t("common.saving") : t("common.save")}
      </button>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
