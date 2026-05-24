import { useState } from "react";
import { DEPARTMENTS } from "../../constants/workflow";
import Modal from "./Modal";

export default function UserModal({ onClose, onSave }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [department, setDepartment] = useState("Kesish");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!username.trim() || !password.trim()) {
      setError("Login va parol majburiy");
      return;
    }

    setSaving(true);
    try {
      await onSave({ username: username.trim(), password: password.trim(), role, department });
      onClose();
    } catch (err) {
      setError(err.message || "Xatolik");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black">Yangi user</h2>
      <div className="space-y-4">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Login"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Parol"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        >
          <option value="operator">Operator</option>
          <option value="admin">Admin</option>
        </select>
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        >
          {DEPARTMENTS.map((d) => (
            <option key={d} value={d}>
              {d}
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
          Saqlash
        </button>
      </div>
    </Modal>
  );
}
