import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import { api, uploadUrl } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { isNativeMobile } from "../mobile/capacitor";

const EMOJI_LIST = ["👍", "✅", "🔥", "😊", "🎉", "📦", "🚚", "⚠️", "❗", "💬"];

function playNotifySound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.value = 0.05;
    osc.start();
    osc.stop(ctx.currentTime + 0.12);
  } catch {
    /* ignore */
  }
}

function avatarColor(name) {
  const colors = [
    "bg-blue-500",
    "bg-green-500",
    "bg-purple-500",
    "bg-orange-500",
    "bg-pink-500",
  ];
  let sum = 0;
  for (let i = 0; i < (name || "").length; i++) sum += name.charCodeAt(i);
  return colors[sum % colors.length];
}

export default function ChatPage() {
  const { user } = useAuth();
  const [rooms, setRooms] = useState([]);
  const [activeRoom, setActiveRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [onlineMap, setOnlineMap] = useState({});
  const [users, setUsers] = useState([]);
  const [typing, setTyping] = useState([]);
  const [unreadTotal, setUnreadTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showUsers, setShowUsers] = useState(false);
  const [soundOn, setSoundOn] = useState(
    () => localStorage.getItem("chat_sound") !== "off"
  );
  const lastMsgId = useRef(0);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const typingTimeout = useRef(null);

  const scrollBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadRooms = useCallback(async () => {
    try {
      const [roomsRes, unreadRes, onlineRes] = await Promise.all([
        api.getChatRooms(),
        api.getChatUnread(),
        api.getChatOnline(),
      ]);
      setRooms(roomsRes.rooms || []);
      setUnreadTotal(unreadRes.total || 0);
      const map = {};
      (onlineRes.operators || []).forEach((o) => {
        map[o.username] = o.is_online;
      });
      setOnlineMap(map);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const loadMessages = useCallback(
    async (roomId, initial = false) => {
      try {
        const since = initial ? 0 : lastMsgId.current;
        const res = await api.getChatMessages(roomId, since);
        const msgs = res.messages || [];
        if (initial) {
          setMessages(msgs);
          lastMsgId.current = msgs.length ? msgs[msgs.length - 1].id : 0;
        } else if (msgs.length) {
          setMessages((prev) => {
            const ids = new Set(prev.map((m) => m.id));
            const added = msgs.filter((m) => !ids.has(m.id));
            if (added.length && soundOn) playNotifySound();
            return [...prev, ...added];
          });
          lastMsgId.current = msgs[msgs.length - 1].id;
        }
        await api.markChatRead(roomId);
        scrollBottom();
      } catch (err) {
        setError(err.message);
      }
    },
    [soundOn]
  );

  useEffect(() => {
    (async () => {
      setLoading(true);
      await loadRooms();
      try {
        const u = await api.getChatUsers();
        setUsers(u);
      } catch {
        /* optional */
      }
      setLoading(false);
    })();
    const t = setInterval(loadRooms, 8000);
    return () => clearInterval(t);
  }, [loadRooms]);

  useEffect(() => {
    if (!activeRoom) return;
    lastMsgId.current = 0;
    setMessages([]);
    loadMessages(activeRoom.id, true);
    const poll = setInterval(() => {
      loadMessages(activeRoom.id, false);
      api.getChatTyping(activeRoom.id).then((r) => setTyping(r.typing || []));
    }, 2500);
    return () => clearInterval(poll);
  }, [activeRoom, loadMessages]);

  const openRoom = (room) => {
    setActiveRoom(room);
    setShowUsers(false);
    setError("");
  };

  const startPrivate = async (username) => {
    try {
      const room = await api.createPrivateChat(username);
      await loadRooms();
      openRoom({ ...room, unread_count: 0 });
      setShowUsers(false);
    } catch (err) {
      setError(err.message);
    }
  };

  const send = async () => {
    if (!activeRoom || !text.trim()) return;
    const content = text.trim();
    setText("");
    try {
      await api.sendChatMessage(activeRoom.id, { content });
      await loadMessages(activeRoom.id, false);
      await loadRooms();
    } catch (err) {
      setError(err.message);
    }
  };

  const onTyping = () => {
    if (!activeRoom) return;
    api.setChatTyping(activeRoom.id, true).catch(() => {});
    clearTimeout(typingTimeout.current);
    typingTimeout.current = setTimeout(() => {
      api.setChatTyping(activeRoom.id, false).catch(() => {});
    }, 2000);
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !activeRoom) return;
    try {
      const up = await api.uploadChatFile(file);
      const isImage = file.type.startsWith("image/");
      await api.sendChatMessage(activeRoom.id, {
        content: file.name,
        message_type: isImage ? "image" : "file",
        attachment_url: up.url,
      });
      await loadMessages(activeRoom.id, false);
    } catch (err) {
      setError(err.message);
    }
    e.target.value = "";
  };

  const onCamera = async () => {
    if (!activeRoom) return;
    try {
      const shot = await Camera.getPhoto({
        resultType: CameraResultType.Uri,
        source: CameraSource.Camera,
        quality: 72,
      });
      if (!shot.webPath) return;

      const response = await fetch(shot.webPath);
      const blob = await response.blob();
      const filename = `camera-${Date.now()}.jpg`;
      const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
      const up = await api.uploadChatFile(file);
      await api.sendChatMessage(activeRoom.id, {
        content: filename,
        message_type: "image",
        attachment_url: up.url,
      });
      await loadMessages(activeRoom.id, false);
    } catch (err) {
      if (err?.message?.includes("User cancelled")) return;
      setError(err?.message || "Kamera xatoligi");
    }
  };

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    localStorage.setItem("chat_sound", next ? "on" : "off");
  };

  if (loading && !rooms.length) return <LoadingSpinner />;

  return (
    <div className="flex h-[calc(100dvh-8rem)] min-h-[480px] flex-col">
      <PageHeader
        title="Ichki chat"
        subtitle={`Operatorlar aloqasi • O'qilmagan: ${unreadTotal}`}
      />
      <ErrorAlert message={error} />

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-3xl border bg-white shadow-sm">
        {/* Sidebar */}
        <aside
          className={`flex w-full flex-col border-r md:w-80 lg:w-96 ${
            activeRoom ? "hidden md:flex" : "flex"
          }`}
        >
          <div className="flex items-center justify-between border-b p-3">
            <span className="text-sm font-bold">Suhbatlar</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowUsers((s) => !s)}
                className="rounded-lg bg-gray-100 px-2 py-1 text-xs font-bold"
              >
                + Shaxsiy
              </button>
              <button
                type="button"
                onClick={toggleSound}
                className="rounded-lg bg-gray-100 px-2 py-1 text-xs"
                title="Ovoz"
              >
                {soundOn ? "🔔" : "🔕"}
              </button>
            </div>
          </div>

          {showUsers && (
            <div className="max-h-40 overflow-y-auto border-b bg-gray-50 p-2">
              {users.map((u) => (
                <button
                  key={u.username}
                  type="button"
                  onClick={() => startPrivate(u.username)}
                  className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-left text-sm hover:bg-white"
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      onlineMap[u.username] ? "bg-green-500" : "bg-gray-300"
                    }`}
                  />
                  {u.username}
                  <span className="text-xs text-gray-400">{u.department}</span>
                </button>
              ))}
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {rooms.map((room) => (
              <button
                key={room.id}
                type="button"
                onClick={() => openRoom(room)}
                className={`flex w-full items-start gap-3 border-b p-3 text-left transition hover:bg-gray-50 ${
                  activeRoom?.id === room.id ? "bg-gray-100" : ""
                }`}
              >
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white text-sm font-bold ${avatarColor(
                    room.name
                  )}`}
                >
                  {room.room_type === "announcement"
                    ? "📢"
                    : (room.name || "?")[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-1">
                    <p className="truncate font-bold text-sm">{room.name}</p>
                    {room.unread_count > 0 && (
                      <span className="rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white">
                        {room.unread_count}
                      </span>
                    )}
                  </div>
                  <p className="truncate text-xs text-gray-500">
                    {room.last_message?.content || "—"}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Messages */}
        <section
          className={`flex min-w-0 flex-1 flex-col ${
            activeRoom ? "flex" : "hidden md:flex"
          }`}
        >
          {activeRoom ? (
            <>
              <div className="flex items-center gap-3 border-b p-3">
                <button
                  type="button"
                  className="md:hidden rounded-lg bg-gray-100 px-2 py-1 text-xs"
                  onClick={() => setActiveRoom(null)}
                >
                  ←
                </button>
                <div>
                  <p className="font-bold">{activeRoom.name}</p>
                  {typing.length > 0 && (
                    <p className="text-xs text-gray-400">
                      {typing.join(", ")} yozmoqda...
                    </p>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((msg) => {
                  const mine = msg.sender_username === user?.username;
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${mine ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-2 ${
                          mine
                            ? "bg-black text-white rounded-br-md"
                            : "bg-gray-100 text-gray-900 rounded-bl-md"
                        }`}
                      >
                        {!mine && (
                          <p className="mb-1 text-xs font-bold opacity-70">
                            {msg.sender_username}
                            <span className="ml-1 font-normal">
                              {msg.sender_department}
                            </span>
                          </p>
                        )}
                        {msg.message_type === "image" && msg.attachment_url ? (
                          <a
                            href={uploadUrl(msg.attachment_url)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <img
                              src={uploadUrl(msg.attachment_url)}
                              alt=""
                              className="max-h-48 rounded-xl"
                            />
                          </a>
                        ) : msg.attachment_url ? (
                          <a
                            href={uploadUrl(msg.attachment_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="underline text-sm"
                          >
                            📎 {msg.content || "Fayl"}
                          </a>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap break-words">
                            {msg.content}
                          </p>
                        )}
                        <p
                          className={`mt-1 text-[10px] ${
                            mine ? "text-gray-300" : "text-gray-400"
                          }`}
                        >
                          {msg.created_at
                            ? new Date(msg.created_at).toLocaleString()
                            : ""}
                        </p>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              <div className="border-t p-3">
                <div className="mb-2 flex flex-wrap gap-1">
                  {EMOJI_LIST.map((em) => (
                    <button
                      key={em}
                      type="button"
                      className="rounded-lg hover:bg-gray-100 px-1"
                      onClick={() => setText((t) => t + em)}
                    >
                      {em}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  {isNativeMobile() && (
                    <button
                      type="button"
                      onClick={onCamera}
                      className="rounded-xl bg-gray-100 px-3 py-2"
                      title="Kamera"
                    >
                      📷
                    </button>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept="image/*,.pdf,.txt,.doc,.docx"
                    onChange={onFile}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded-xl bg-gray-100 px-3 py-2"
                  >
                    📎
                  </button>
                  <input
                    value={text}
                    onChange={(e) => {
                      setText(e.target.value);
                      onTyping();
                    }}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                    placeholder="Xabar yozing..."
                    className="flex-1 rounded-2xl border px-4 py-2 text-sm"
                  />
                  <button
                    type="button"
                    onClick={send}
                    className="rounded-2xl bg-black px-5 py-2 font-bold text-white"
                  >
                    Yuborish
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-gray-400">
              Suhbat tanlang
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
