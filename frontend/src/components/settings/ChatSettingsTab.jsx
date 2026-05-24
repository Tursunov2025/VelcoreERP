import { useState } from "react";
import Card from "../ui/Card";

export default function ChatSettingsTab() {
  const [sound, setSound] = useState(
    () => localStorage.getItem("chat_sound") !== "off"
  );
  const [moderationNote, setModerationNote] = useState("");

  const saveSound = (on) => {
    setSound(on);
    localStorage.setItem("chat_sound", on ? "on" : "off");
  };

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="mb-3 font-bold">Chat bildirishnomalari</h2>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={sound}
            onChange={(e) => saveSound(e.target.checked)}
          />
          <span className="text-sm">Yangi xabar uchun ovozli signal</span>
        </label>
      </Card>

      <Card>
        <h2 className="mb-3 font-bold">Moderatsiya</h2>
        <p className="mb-3 text-sm text-gray-600">
          Admin xabarlarni chat sahifasida o&apos;chirishi mumkin (API: DELETE
          /chat/messages/&#123;id&#125;). E&apos;lonlar kanaliga faqat admin yozadi.
        </p>
        <textarea
          value={moderationNote}
          onChange={(e) => setModerationNote(e.target.value)}
          placeholder="Ichki moderatsiya qoidalari (ixtiyoriy)..."
          className="w-full rounded-2xl border p-3 text-sm min-h-[100px]"
        />
        <button
          type="button"
          onClick={() => {
            localStorage.setItem("chat_moderation_note", moderationNote);
            alert("Saqlandi");
          }}
          className="mt-3 rounded-xl bg-black px-4 py-2 text-sm font-bold text-white"
        >
          Saqlash
        </button>
      </Card>
    </div>
  );
}
