import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { isTruthySetting, NOTIFICATION_EVENTS } from "../../constants/permissions";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";

export default function NotificationsTab() {
  const { t } = useLocale();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setSettings(await api.adminGetNotificationSettings());
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
      await api.adminUpdateNotificationSettings(settings);
      setToast(t("legacySettings.notificationsSaved"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const toggle = (key) => {
    const current = isTruthySetting(settings[key]);
    setSettings({ ...settings, [key]: current ? "false" : "true" });
  };

  if (loading) return <p>{t("common.loading")}</p>;

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">{t("settingsNav.notifications")}</h2>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isTruthySetting(settings.notifications_enabled)}
            onChange={() => toggle("notifications_enabled")}
            className="h-5 w-5 rounded"
          />
          <span className="font-medium">{t("legacySettings.allNotifications")}</span>
        </label>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isTruthySetting(settings.telegram_notifications_enabled)}
            onChange={() => toggle("telegram_notifications_enabled")}
            className="h-5 w-5 rounded"
          />
          <span className="font-medium">{t("legacySettings.sendToTelegram")}</span>
        </label>
        <hr />
        <p className="text-sm text-gray-500">{t("legacySettings.eventSettings")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {NOTIFICATION_EVENTS.map((event) => {
            const key = `notify_${event.id}`;
            return (
              <label key={event.id} className="flex items-center gap-3 rounded-xl bg-gray-50 px-4 py-3">
                <input
                  type="checkbox"
                  checked={isTruthySetting(settings[key])}
                  onChange={() => toggle(key)}
                  className="h-5 w-5 rounded"
                />
                <span className="text-sm">{t(`legacySettings.notificationEvents.${event.id}`)}</span>
              </label>
            );
          })}
        </div>
        <button
          type="button"
          onClick={save}
          className="w-full rounded-2xl bg-black py-3 font-bold text-white"
        >
          {t("common.save")}
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
