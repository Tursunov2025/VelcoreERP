import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { DEFAULT_LOCALE, translate } from "../i18n/translations";
import { readUiPrefs, writeUiPrefs } from "../utils/uiPrefs";
import { useAuth } from "./AuthContext";

const LocaleContext = createContext(null);

function resolveLanguage(brandingLang, userLang, localLang) {
  return userLang || localLang || brandingLang || DEFAULT_LOCALE;
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
        if (prefs.ui_language) setLanguageState(prefs.ui_language);
        if (prefs.ui_theme) setThemeState(prefs.ui_theme);
        if (prefs.ui_clock_format) setClockFormatState(prefs.ui_clock_format);
        writeUiPrefs({
          language: prefs.ui_language || language,
          theme: prefs.ui_theme || theme,
          clock_format: prefs.ui_clock_format || clockFormat,
        });
      })
      .catch(() => {});
  }, [isLoggedIn]);

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
      setLanguageState(lang);
      persist({ language: lang, theme, clock_format: clockFormat });
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

  const t = useCallback((key) => translate(language, key), [language]);

  const value = useMemo(
    () => ({
      language,
      theme,
      clockFormat,
      clockTimezone: brandingDefaults.clock_timezone || "Asia/Tashkent",
      setLanguage,
      setTheme,
      setClockFormat,
      applySystemDefaults,
      t,
    }),
    [
      language,
      theme,
      clockFormat,
      brandingDefaults.clock_timezone,
      setLanguage,
      setTheme,
      setClockFormat,
      applySystemDefaults,
      t,
    ]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
