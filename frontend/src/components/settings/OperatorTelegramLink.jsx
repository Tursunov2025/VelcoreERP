import { useEffect, useState } from "react";
import { api } from "../../api/client";
import Toast from "../ui/Toast";

export default function OperatorTelegramLink() {
  const [status, setStatus] = useState(null);
  const [code, setCode] = useState("");
  const [linkCode, setLinkCode] = useState("");
  const [form, setForm] = useState({ telegram_id: "", telegram_username: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [expanded, setExpanded] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setStatus(await api.getTelegramStatus());
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const requestCode = async () => {
    setBusy(true);
    try {
      const res = await api.generateTelegramLinkCode();
      setLinkCode(res.code);
      setExpanded(true);
      setToast("Kod yaratildi — 15 daqiqa amal qiladi");
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (!form.telegram_id.trim()) {
      setToast("Telegram ID kiriting");
      return;
    }
    setBusy(true);
    try {
      await api.verifyTelegramLink({
        code: code || linkCode,
        telegram_id: form.telegram_id.trim(),
        telegram_username: form.telegram_username.trim(),
      });
      setToast("Telegram bog'landi");
      setLinkCode("");
      setCode("");
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    try {
      await api.unlinkTelegram();
      setToast("Telegram uzildi");
      load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return null;

  return (
    <div className="mt-4 rounded-2xl bg-white/10 p-4 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-left font-semibold"
      >
        <span>📱 Telegram</span>
        <span className="text-xs text-gray-400">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="mt-3 space-y-3">
          {status?.linked ? (
            <>
              <p className="text-xs text-gray-300">
                Bog&apos;langan: @{status.telegram_username || "—"} ({status.telegram_id})
              </p>
              <button
                type="button"
                onClick={unlink}
                disabled={busy}
                className="w-full rounded-xl bg-red-500/80 py-2 text-xs font-bold"
              >
                Uzish
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={requestCode}
                disabled={busy}
                className="w-full rounded-xl bg-white/20 py-2 text-xs font-bold"
              >
                Tasdiqlash kodi olish
              </button>
              {linkCode && (
                <p className="rounded-xl bg-black/30 px-3 py-2 text-center font-mono text-lg tracking-widest">
                  {linkCode}
                </p>
              )}
              <input
                value={code || linkCode}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Kod"
                className="w-full rounded-xl border-0 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-gray-500"
              />
              <input
                value={form.telegram_id}
                onChange={(e) => setForm({ ...form, telegram_id: e.target.value })}
                placeholder="Telegram ID"
                className="w-full rounded-xl border-0 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-gray-500"
              />
              <input
                value={form.telegram_username}
                onChange={(e) => setForm({ ...form, telegram_username: e.target.value })}
                placeholder="@username"
                className="w-full rounded-xl border-0 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-gray-500"
              />
              <button
                type="button"
                onClick={verify}
                disabled={busy}
                className="w-full rounded-xl bg-white py-2 text-xs font-bold text-black"
              >
                Bog&apos;lash
              </button>
            </>
          )}
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
