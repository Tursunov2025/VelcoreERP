export const UI_PREFS_KEY = "azmus_ui_prefs";

export const DEFAULT_UI_PREFS = {
  language: "uz_latn",
  theme: "light",
  clock_format: "24h",
};

export function readUiPrefs() {
  try {
    const raw = localStorage.getItem(UI_PREFS_KEY);
    return raw ? { ...DEFAULT_UI_PREFS, ...JSON.parse(raw) } : { ...DEFAULT_UI_PREFS };
  } catch {
    return { ...DEFAULT_UI_PREFS };
  }
}

export function writeUiPrefs(prefs) {
  const merged = { ...readUiPrefs(), ...prefs };
  localStorage.setItem(UI_PREFS_KEY, JSON.stringify(merged));
  return merged;
}
