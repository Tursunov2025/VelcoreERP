import { useEffect, useState } from "react";
import { api } from "../../api/client";
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

  if (loading) return <p>Yuklanmoqda...</p>;

  const fields = [
    { key: "company_phone", label: "Telefon" },
    { key: "jwt_access_minutes", label: "JWT Access (daqiqa)" },
    { key: "jwt_refresh_days", label: "JWT Refresh (kun)" },
    { key: "auto_backup_enabled", label: "Avto backup (true/false)" },
    { key: "auto_backup_interval_hours", label: "Avto backup interval (soat)" },
  ];

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">Tizim sozlamalari</h2>
      <p className="mb-4 text-sm text-gray-500">
        Dastur nomi va logolar &quot;Tashqi ko&apos;rinish&quot; bo&apos;limida boshqariladi.
      </p>
      <div className="space-y-4 rounded-2xl border bg-white p-6">
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
          className="brand-btn w-full py-3 font-bold text-white"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          Saqlash
        </button>
      </div>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
