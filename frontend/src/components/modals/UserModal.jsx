import { useState } from "react";
import Modal from "./Modal";

export default function UserModal({ onClose, onSave }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!username.trim() || !password.trim()) {
      setError("Login va parol majburiy");
      return;
    }

    setSaving(true);
    setError("");

    try {
      await onSave({
        username: username.trim(),
        password: password.trim(),
        role,
      });
      onClose();
    } catch (err) {
      setError(err.message || "Foydalanuvchini yaratib bo'lmadi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black md:text-3xl">Yangi user</h2>

      <div className="space-y-4">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Login"
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        />

        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Parol"
          type="password"
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        />

        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        >
          <option value="operator">Operator</option>
          <option value="admin">Admin</option>
        </select>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded-2xl bg-black py-4 font-bold text-white transition hover:bg-gray-800 disabled:opacity-60"
        >
          {saving ? "Saqlanmoqda..." : "Saqlash"}
        </button>
      </div>
    </Modal>
  );
}
