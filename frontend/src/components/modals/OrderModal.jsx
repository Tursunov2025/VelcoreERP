import { useState } from "react";
import { api } from "../../api/client";
import Modal from "./Modal";

export default function OrderModal({ onClose, onSave }) {
  const [client, setClient] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [comment, setComment] = useState("");
  const [destination, setDestination] = useState("");
  const [estimatedFinish, setEstimatedFinish] = useState("");
  const [imageUrls, setImageUrls] = useState([]);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleImage = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setUploading(true);
    try {
      const result = await api.uploadImage(file);
      setImageUrls((prev) => [...prev, result.url]);
    } catch (err) {
      setError(err.message || "Rasm yuklanmadi");
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    if (!client.trim() || !amount.trim()) {
      setError("Mijoz nomi va summa majburiy");
      return;
    }

    setSaving(true);
    setError("");

    try {
      await onSave({
        client: client.trim(),
        phone: phone.trim(),
        amount: amount.trim(),
        comment: comment.trim(),
        destination: destination.trim(),
        image_urls: imageUrls,
        image_url: imageUrls[0] || null,
        estimated_finish_at: estimatedFinish
          ? new Date(estimatedFinish).toISOString()
          : null,
      });
      onClose();
    } catch (err) {
      setError(err.message || "Zakazni saqlab bo'lmadi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black">Yangi zakaz</h2>
      <p className="mb-4 text-sm text-gray-500">Avtomatik Kesish bo&apos;limiga tushadi</p>

      <div className="space-y-4">
        <input
          value={client}
          onChange={(e) => setClient(e.target.value)}
          placeholder="Mijoz nomi *"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Telefon"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Summa *"
          type="number"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="Manzil / destination"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Izoh"
          rows={2}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          type="date"
          value={estimatedFinish}
          onChange={(e) => setEstimatedFinish(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input type="file" accept="image/*" onChange={handleImage} />
        {uploading && <p className="text-sm text-gray-500">Yuklanmoqda...</p>}
        {preview && (
          <img src={preview} alt="" className="h-24 rounded-2xl object-cover" />
        )}
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || uploading}
          className="w-full rounded-2xl bg-black py-4 font-bold text-white disabled:opacity-60"
        >
          {saving ? "Saqlanmoqda..." : "Saqlash"}
        </button>
      </div>
    </Modal>
  );
}
