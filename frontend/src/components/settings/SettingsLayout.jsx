const TABS = [
  { id: "users", label: "Foydalanuvchilar", icon: "👥" },
  { id: "appearance", label: "Tashqi ko'rinish", icon: "🎨" },
  { id: "permissions", label: "Ruxsatlar", icon: "🔐" },
  { id: "telegram", label: "Telegram", icon: "📱" },
  { id: "notifications", label: "Bildirishnomalar", icon: "🔔" },
  { id: "orders", label: "Zakazlar", icon: "📋" },
  { id: "shipments", label: "Yuk arxivi", icon: "🚚" },
  { id: "search", label: "Qidiruv", icon: "🔍" },
  { id: "online", label: "Online", icon: "🟢" },
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "system", label: "Tizim", icon: "⚙️" },
  { id: "audit", label: "Audit", icon: "📜" },
  { id: "backup", label: "Backup", icon: "💾" },
];

export default function SettingsLayout({ activeTab, onTabChange, children }) {
  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="lg:w-56 shrink-0">
        <nav className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`flex shrink-0 items-center gap-2 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition ${
                activeTab === tab.id
                  ? "bg-black text-white"
                  : "bg-white text-gray-700 hover:bg-gray-100"
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export { TABS };
