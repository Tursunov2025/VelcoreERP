import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { DASHBOARD_WIDGET_DEFS, DEFAULT_DASHBOARD_WIDGETS } from "../../constants/controlCenter";
import { invalidateUiConfigCache } from "../../hooks/useUiConfig";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

export default function DashboardWidgetsTab() {
  const { t } = useLocale();
  const [widgets, setWidgets] = useState(DEFAULT_DASHBOARD_WIDGETS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    api
      .adminGetExecutiveSettings()
      .then((data) => {
        try {
          const parsed = JSON.parse(data.dashboard_widgets_json || "[]");
          if (Array.isArray(parsed) && parsed.length) setWidgets(parsed);
        } catch {
          /* defaults */
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id) => {
    setWidgets((prev) =>
      prev.map((w) => (w.id === id ? { ...w, enabled: !w.enabled } : w))
    );
  };

  const move = (id, dir) => {
    setWidgets((prev) => {
      const sorted = [...prev].sort((a, b) => (a.order || 0) - (b.order || 0));
      const idx = sorted.findIndex((w) => w.id === id);
      const swap = idx + dir;
      if (swap < 0 || swap >= sorted.length) return prev;
      const a = sorted[idx];
      const b = sorted[swap];
      return prev.map((w) => {
        if (w.id === a.id) return { ...w, order: b.order };
        if (w.id === b.id) return { ...w, order: a.order };
        return w;
      });
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const ordered = [...widgets].sort((a, b) => (a.order || 0) - (b.order || 0));
      await api.adminUpdateExecutiveSettings({
        dashboard_widgets_json: JSON.stringify(ordered),
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

  const sorted = [...widgets].sort((a, b) => (a.order || 0) - (b.order || 0));

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("controlCenter.widgetsTitle")}</h2>
      <p className="mb-4 text-sm text-[var(--brand-muted)]">{t("controlCenter.widgetsSubtitle")}</p>
      <div className="space-y-2">
        {sorted.map((w) => {
          const def = DASHBOARD_WIDGET_DEFS.find((d) => d.id === w.id);
          return (
            <div
              key={w.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border bg-white px-4 py-3"
            >
              <input
                type="checkbox"
                checked={w.enabled !== false}
                onChange={() => toggle(w.id)}
                className="h-5 w-5"
              />
              <span className="flex-1 text-sm font-semibold">
                {def ? t(def.labelKey) : w.id}
              </span>
              <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => move(w.id, -1)}>
                ↑
              </button>
              <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => move(w.id, 1)}>
                ↓
              </button>
            </div>
          );
        })}
      </div>
      <button
        type="button"
        disabled={saving}
        onClick={save}
        className="brand-btn mt-6 rounded-xl px-6 py-3 font-bold text-white"
        style={{ backgroundColor: "var(--brand-button)" }}
      >
        {saving ? t("common.saving") : t("common.save")}
      </button>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
