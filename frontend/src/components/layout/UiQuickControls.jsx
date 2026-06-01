import { LANGUAGE_OPTIONS } from "../../i18n/translations";
import { useLocale } from "../../context/LocaleContext";

const THEMES = [
  { id: "light", labelKey: "appearance.themeLight" },
  { id: "dark", labelKey: "appearance.themeDark" },
  { id: "auto", labelKey: "appearance.themeAuto" },
];

export default function UiQuickControls({ compact = false, variant = "dark" }) {
  const { language, theme, setLanguage, setTheme, t } = useLocale();

  const selectClass =
    variant === "dark"
      ? "rounded-lg border bg-white/10 px-2 py-1 text-xs text-inherit"
      : "rounded-lg border border-gray-300 bg-white px-2 py-1 text-xs text-gray-800";

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        <select
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          className={selectClass}
          aria-label={t("appearance.theme")}
        >
          {THEMES.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className={`${selectClass} max-w-[92px]`}
          aria-label={t("appearance.language")}
        >
          {LANGUAGE_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      <select
        value={theme}
        onChange={(e) => setTheme(e.target.value)}
        className="rounded-xl border px-3 py-2 text-sm"
      >
        {THEMES.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {t(opt.labelKey)}
          </option>
        ))}
      </select>
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
        className="rounded-xl border px-3 py-2 text-sm"
      >
        {LANGUAGE_OPTIONS.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
