import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { DEFAULT_LOCALE, normalizeLocale, translate } from "../i18n/translations";
import { readUiPrefs, writeUiPrefs } from "../utils/uiPrefs";
import { useAuth } from "./AuthContext";

const LocaleContext = createContext(null);

function resolveLanguage(brandingLang, userLang, localLang) {
  return normalizeLocale(userLang || localLang || brandingLang || DEFAULT_LOCALE);
}

function resolveTheme(brandingTheme, userTheme, localTheme) {
  return userTheme || localTheme || brandingTheme || "light";
}

function resolveClockFormat(brandingFmt, userFmt, localFmt) {
  return userFmt || localFmt || brandingFmt || "24h";
}

export function LocaleProvider({ children, brandingDefaults = {} }) {
  const { isLoggedIn } = useAuth();
  const [language, setLanguageState] = useState(() =>
    resolveLanguage(brandingDefaults.language, null, readUiPrefs().language)
  );
  const [theme, setThemeState] = useState(() =>
    resolveTheme(brandingDefaults.theme_mode, null, readUiPrefs().theme)
  );
  const [clockFormat, setClockFormatState] = useState(() =>
    resolveClockFormat(brandingDefaults.clock_format, null, readUiPrefs().clock_format)
  );

  useEffect(() => {
    const local = readUiPrefs();
    setLanguageState(
      resolveLanguage(brandingDefaults.language, null, local.language)
    );
    setThemeState(resolveTheme(brandingDefaults.theme_mode, null, local.theme));
    setClockFormatState(
      resolveClockFormat(brandingDefaults.clock_format, null, local.clock_format)
    );
  }, [brandingDefaults.language, brandingDefaults.theme_mode, brandingDefaults.clock_format]);

  useEffect(() => {
    if (!isLoggedIn) return;
    api
      .getUiPreferences()
      .then((prefs) => {
        const effectiveLanguage = resolveLanguage(
          brandingDefaults.language,
          prefs.ui_language,
          null
        );
        const effectiveTheme = resolveTheme(
          brandingDefaults.theme_mode,
          prefs.ui_theme,
          null
        );
        const effectiveClockFormat = resolveClockFormat(
          brandingDefaults.clock_format,
          prefs.ui_clock_format,
          null
        );
        setLanguageState(effectiveLanguage);
        setThemeState(effectiveTheme);
        setClockFormatState(effectiveClockFormat);
        writeUiPrefs({
          language: prefs.ui_language || effectiveLanguage,
          theme: prefs.ui_theme ?? null,
          clock_format: prefs.ui_clock_format || effectiveClockFormat,
        });
      })
      .catch(() => {});
  }, [
    brandingDefaults.clock_format,
    brandingDefaults.language,
    brandingDefaults.theme_mode,
    isLoggedIn,
  ]);

  useEffect(() => {
    document.documentElement.lang = language === "ru" ? "ru" : "uz";
  }, [language]);

  const persist = useCallback(
    async (next) => {
      writeUiPrefs(next);
      if (isLoggedIn) {
        try {
          await api.updateUiPreferences({
            ui_language: next.language,
            ui_theme: next.theme,
            ui_clock_format: next.clock_format,
          });
        } catch {
          /* localStorage still holds prefs */
        }
      }
    },
    [isLoggedIn]
  );

  const setLanguage = useCallback(
    (lang) => {
      const normalized = normalizeLocale(lang);
      setLanguageState(normalized);
      persist({ language: normalized, theme, clock_format: clockFormat });
    },
    [theme, clockFormat, persist]
  );

  const setTheme = useCallback(
    (mode) => {
      setThemeState(mode);
      persist({ language, theme: mode, clock_format: clockFormat });
    },
    [language, clockFormat, persist]
  );

  const useOrganizationTheme = useCallback(async () => {
    const inherited = brandingDefaults.theme_mode || "light";
    setThemeState(inherited);
    writeUiPrefs({ language, theme: null, clock_format: clockFormat });
    if (isLoggedIn) {
      try {
        await api.updateUiPreferences({ inherit_theme: true });
      } catch {
        /* the local inheritance choice remains effective for this browser */
      }
    }
  }, [brandingDefaults.theme_mode, clockFormat, isLoggedIn, language]);

  const setClockFormat = useCallback(
    (fmt) => {
      setClockFormatState(fmt);
      persist({ language, theme, clock_format: fmt });
    },
    [language, theme, persist]
  );

  const applySystemDefaults = useCallback((defaults) => {
    const lang = defaults.language || DEFAULT_LOCALE;
    const th = defaults.theme_mode || "light";
    const fmt = defaults.clock_format || "24h";
    setLanguageState(lang);
    setThemeState(th);
    setClockFormatState(fmt);
    writeUiPrefs({ language: lang, theme: th, clock_format: fmt });
  }, []);

  const t = useCallback((key, params) => translate(language, key, params), [language]);
  const localeTag = language === "ru" ? "ru-RU" : "uz-UZ";
  const formatNumber = useCallback((value, options) => new Intl.NumberFormat(localeTag, options).format(value), [localeTag]);
  const formatDate = useCallback((value, options) => new Intl.DateTimeFormat(localeTag, options).format(new Date(value)), [localeTag]);
  const formatDateTime = useCallback((value, options) => new Intl.DateTimeFormat(localeTag, { dateStyle: "medium", timeStyle: "short", ...options }).format(new Date(value)), [localeTag]);
  const formatCurrency = useCallback((value, currency = "UZS", options = {}) => new Intl.NumberFormat(localeTag, { style: "currency", currency, ...options }).format(value), [localeTag]);
  const formatPercent = useCallback((value, options) => new Intl.NumberFormat(localeTag, { style: "percent", ...options }).format(value), [localeTag]);

  const value = useMemo(
    () => ({
      language,
      theme,
      clockFormat,
      clockTimezone: brandingDefaults.clock_timezone || "Asia/Tashkent",
      setLanguage,
      setTheme,
      useOrganizationTheme,
      setClockFormat,
      applySystemDefaults,
      t,
      localeTag,
      formatNumber,
      formatDate,
      formatDateTime,
      formatCurrency,
      formatPercent,
    }),
    [
      language,
      theme,
      clockFormat,
      brandingDefaults.clock_timezone,
      setLanguage,
      setTheme,
      useOrganizationTheme,
      setClockFormat,
      applySystemDefaults,
      t,
      localeTag,
      formatNumber,
      formatDate,
      formatDateTime,
      formatCurrency,
      formatPercent,
    ]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
