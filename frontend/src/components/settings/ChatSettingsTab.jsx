import { useState } from "react";
import Card from "../ui/Card";
import { useLocale } from "../../context/LocaleContext";

export default function ChatSettingsTab() {
  const { t } = useLocale();
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
        <h2 className="mb-3 font-bold">{t("legacySettings.chatNotifications")}</h2>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={sound}
            onChange={(e) => saveSound(e.target.checked)}
          />
          <span className="text-sm">{t("legacySettings.chatSound")}</span>
        </label>
      </Card>

      <Card>
        <h2 className="mb-3 font-bold">{t("legacySettings.moderation")}</h2>
        <p className="mb-3 text-sm text-gray-600">
          {t("legacySettings.moderationDescription")}
        </p>
        <textarea
          value={moderationNote}
          onChange={(e) => setModerationNote(e.target.value)}
          placeholder={t("legacySettings.moderationPlaceholder")}
          className="w-full rounded-2xl border p-3 text-sm min-h-[100px]"
        />
        <button
          type="button"
          onClick={() => {
            localStorage.setItem("chat_moderation_note", moderationNote);
            alert(t("legacySettings.saved"));
          }}
          className="mt-3 rounded-xl bg-black px-4 py-2 text-sm font-bold text-white"
        >
          {t("common.save")}
        </button>
      </Card>
    </div>
  );
}
