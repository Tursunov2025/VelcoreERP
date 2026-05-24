import { useState } from "react";
import Modal from "./Modal";

export default function OrderModal({ onClose, onSave }) {
  const [client, setClient] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!client.trim() || !amount.trim()) {
      setError("Mijoz nomi va summa majburiy");
      return;
    }

    setSaving(true);
    setError("");

    try {
      await onSave({ client: client.trim(), phone: phone.trim(), amount: amount.trim() });
      onClose();
    } catch (err) {
      setError(err.message || "Zakazni saqlab bo'lmadi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black md:text-3xl">Yangi zakaz</h2>

      <div className="space-y-4">
        <input
          value={client}
          onChange={(e) => setClient(e.target.value)}
          placeholder="Mijoz nomi"
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        />

        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Telefon"
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        />

        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Summa"
          type="number"
          min="0"
          className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
        />

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
