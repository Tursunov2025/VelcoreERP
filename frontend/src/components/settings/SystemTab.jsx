import { useEffect, useState } from "react";
import { api } from "../../api/client";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";

export default function SystemTab() {
  const { t } = useLocale();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setSettings(await api.adminGetSystemSettings());
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
    try {
      await api.adminUpdateSystemSettings(settings);
      setToast(t("legacySettings.saved"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  if (loading) return <p>{t("common.loading")}</p>;

  const fields = [
    { key: "company_phone" }, { key: "jwt_access_minutes" }, { key: "jwt_refresh_days" },
    { key: "auto_backup_enabled" }, { key: "auto_backup_interval_hours" },
  ];

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">{t("legacySettings.systemTitle")}</h2>
      <p className="mb-4 text-sm text-gray-500">
        {t("legacySettings.systemDescription")}
      </p>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
        {fields.map(({ key }) => (
          <div key={key}>
            <label className="mb-1 block text-sm text-gray-600">{t(`legacySettings.domainFields.${key}`)}</label>
            <input
              value={settings[key] || ""}
              onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}
              className="w-full rounded-xl border px-4 py-3"
            />
          </div>
        ))}
        <button
          type="button"
          onClick={save}
          className="brand-btn w-full py-3 font-bold text-white"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("common.save")}
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
