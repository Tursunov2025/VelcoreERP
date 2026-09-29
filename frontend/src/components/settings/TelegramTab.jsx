import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { isTruthySetting } from "../../constants/permissions";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";

export default function TelegramTab() {
  const { t } = useLocale();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setSettings(await api.adminGetTelegramSettings());
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
      await api.adminUpdateTelegramSettings(settings);
      setToast(t("legacySettings.telegramSaved"));
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const testMessage = async () => {
    setTesting(true);
    try {
      await api.adminTestTelegram();
      setToast(t("legacySettings.testSent"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <p>{t("common.loading")}</p>;

  const notificationsOn = isTruthySetting(settings.telegram_notifications_enabled);
  const globalOn = isTruthySetting(settings.notifications_enabled);

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">{t("legacySettings.telegramTitle")}</h2>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
        <div>
          <label className="mb-1 block text-sm text-gray-600">{t("legacySettings.botToken")}</label>
          <input
            value={settings.telegram_bot_token || ""}
            onChange={(e) =>
              setSettings({ ...settings, telegram_bot_token: e.target.value })
            }
            placeholder="123456:ABC-DEF..."
            className="w-full rounded-xl border px-4 py-3 font-mono text-sm"
          />
          <p className="mt-1 text-xs text-gray-400">
            {t("legacySettings.tokenHint")}
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm text-gray-600">{t("legacySettings.chatId")}</label>
          <input
            value={settings.telegram_chat_id || ""}
            onChange={(e) =>
              setSettings({ ...settings, telegram_chat_id: e.target.value })
            }
            placeholder="-1001234567890"
            className="w-full rounded-xl border px-4 py-3 font-mono text-sm"
          />
        </div>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={globalOn}
            onChange={(e) =>
              setSettings({
                ...settings,
                notifications_enabled: e.target.checked ? "true" : "false",
              })
            }
            className="h-5 w-5 rounded"
          />
          <span className="text-sm font-medium">{t("legacySettings.notificationsEnabled")}</span>
        </label>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={notificationsOn}
            onChange={(e) =>
              setSettings({
                ...settings,
                telegram_notifications_enabled: e.target.checked ? "true" : "false",
              })
            }
            className="h-5 w-5 rounded"
          />
          <span className="text-sm font-medium">{t("legacySettings.sendViaTelegram")}</span>
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={save}
            className="flex-1 rounded-2xl bg-black py-3 font-bold text-white"
          >
            {t("common.save")}
          </button>
          <button
            type="button"
            onClick={testMessage}
            disabled={testing}
            className="flex-1 rounded-2xl border-2 border-black py-3 font-bold disabled:opacity-50"
          >
            {testing ? t("legacySettings.sending") : t("legacySettings.testMessage")}
          </button>
        </div>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
