import { useEffect, useState } from "react";
import { api, uploadUrl } from "../../api/client";
import Toast from "../ui/Toast";

export default function SystemTab() {
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
      setToast("Sozlamalar saqlandi");
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await api.uploadImage(file);
      setSettings({ ...settings, company_logo_url: res.url });
      setToast("Logo yuklandi");
    } catch (err) {
      setToast(err.message);
    }
  };

  if (loading) return <p>Yuklanmoqda...</p>;

  const fields = [
    { key: "company_name", label: "Kompaniya nomi" },
    { key: "company_phone", label: "Telefon" },
    { key: "telegram_chat_id", label: "Telegram Chat ID" },
    { key: "telegram_bot_token", label: "Telegram Bot Token" },
    { key: "jwt_access_minutes", label: "JWT Access (daqiqa)" },
    { key: "jwt_refresh_days", label: "JWT Refresh (kun)" },
    { key: "notifications_enabled", label: "Bildirishnomalar (true/false)" },
    { key: "auto_backup_enabled", label: "Avto backup (true/false)" },
    { key: "auto_backup_interval_hours", label: "Avto backup interval (soat)" },
  ];

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">Tizim sozlamalari</h2>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
        {settings.company_logo_url && (
          <img
            src={uploadUrl(settings.company_logo_url)}
            alt="Logo"
            className="h-16 object-contain"
          />
        )}
        <div>
          <label className="text-sm text-gray-500">Logo yuklash</label>
          <input type="file" accept="image/*" onChange={uploadLogo} className="mt-1" />
        </div>
        {fields.map(({ key, label }) => (
          <div key={key}>
            <label className="mb-1 block text-sm text-gray-600">{label}</label>
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
          className="w-full rounded-2xl bg-black py-3 font-bold text-white"
        >
          Saqlash
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
