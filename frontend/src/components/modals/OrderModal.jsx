import { useState } from "react";
import { api } from "../../api/client";
import Modal from "./Modal";
import { useLocale } from "../../context/LocaleContext";
import LocalizedFileInput from "../ui/LocalizedFileInput";

export default function OrderModal({ onClose, onSave }) {
  const { t } = useLocale();
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
      setError(err.message || t("orders.imageUploadFailed"));
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    if (!client.trim() || !amount.trim()) {
      setError(t("orders.customerAmountRequired"));
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
      setError(err.message || t("orders.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <h2 className="mb-6 text-2xl font-black">{t("orders.newOrder")}</h2>
      <p className="mb-4 text-sm text-gray-500">{t("orders.autoCuttingStage")}</p>

      <div className="space-y-4">
        <input
          value={client}
          onChange={(e) => setClient(e.target.value)}
          placeholder={t("orders.customerRequired")}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder={t("orders.phone")}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder={t("orders.amountRequired")}
          type="number"
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder={t("orders.destination")}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={t("orders.comment")}
          rows={2}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <input
          type="date"
          value={estimatedFinish}
          onChange={(e) => setEstimatedFinish(e.target.value)}
          className="w-full rounded-2xl border px-5 py-4"
        />
        <LocalizedFileInput accept="image/*" onChange={handleImage} disabled={uploading} />
        {uploading && <p className="text-sm text-gray-500">{t("common.loading")}</p>}
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
          {saving ? t("common.saving") : t("common.save")}
        </button>
      </div>
    </Modal>
  );
}
