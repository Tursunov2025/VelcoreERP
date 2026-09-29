import { useState } from "react";
import { DEPARTMENTS } from "../../constants/workflow";
import Modal from "./Modal";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";

export default function UserModal({ onClose, onSave }) {
  const { t } = useLocale();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [department, setDepartment] = useState("Kesish");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!username.trim() || !password.trim()) {
      setError(t("users.loginPasswordRequired"));
      return;
    }

    setSaving(true);
    try {
      await onSave({ username: username.trim(), password: password.trim(), role, department });
      onClose();
    } catch (err) {
      setError(err.message || t("errors.generic"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black">{t("users.createUser")}</h2>
      <div className="space-y-4">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder={t("users.username")}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("users.password")}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        >
          <option value="operator">{t("roleNames.operator")}</option>
          <option value="admin">{t("roleNames.admin")}</option>
        </select>
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        >
          {DEPARTMENTS.map((d) => (
            <option key={d} value={d}>
              {localizedCanonical(t, "productionStages", d)}
            </option>
          ))}
        </select>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded-2xl bg-black py-4 font-bold text-white"
        >
          {saving ? t("common.saving") : t("common.save")}
        </button>
      </div>
    </Modal>
  );
}
