import { useEffect, useState } from "react";
import Toast from "../ui/Toast";

/**
 * Reusable mobile-first settings form for admin domain tabs.
 */
export default function DomainSettingsForm({
  title,
  subtitle,
  fields,
  loadSettings,
  saveSettings,
}) {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setSettings(await loadSettings());
    } catch (e) {
      setToast(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setBusy(true);
    setToast("");
    try {
      await saveSettings(settings);
      setToast("Sozlamalar saqlandi");
      await load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <p className="py-8 text-center text-[var(--brand-muted)]">Yuklanmoqda...</p>;

  return (
    <div className="pb-8">
      <h2 className="mb-2 text-xl font-black">{title}</h2>
      {subtitle ? <p className="mb-4 text-sm text-[var(--brand-muted)]">{subtitle}</p> : null}
      <div className="space-y-4 rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
        {fields.map(({ key, label, type = "text", placeholder, hint }) => (
          <div key={key}>
            <label className="mb-1 block text-sm font-semibold">{label}</label>
            {hint ? <p className="mb-1 text-xs text-[var(--brand-muted)]">{hint}</p> : null}
            {type === "textarea" ? (
              <textarea
                value={settings[key] || ""}
                onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}
                rows={4}
                placeholder={placeholder}
                className="min-h-[120px] w-full rounded-xl border px-4 py-3 font-mono text-sm"
                disabled={busy}
              />
            ) : (
              <input
                type={type}
                value={settings[key] || ""}
                onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}
                placeholder={placeholder}
                className="min-h-[48px] w-full rounded-xl border px-4 py-3"
                disabled={busy}
              />
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="min-h-[48px] w-full rounded-xl font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          Saqlash
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
