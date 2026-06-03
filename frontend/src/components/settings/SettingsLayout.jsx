const CENTRAL_TABS = [
  { id: "company", label: "Kompaniya", icon: "🏢" },
  { id: "production", label: "Ishlab chiqarish", icon: "🏭" },
  { id: "telegram", label: "Telegram", icon: "📱" },
  { id: "warehouse", label: "Ombor", icon: "📦" },
  { id: "materials", label: "Xom ashyo", icon: "🧱" },
  { id: "costing", label: "Tannarx", icon: "💰" },
  { id: "appearance", label: "UI", icon: "🎨" },
  { id: "backupSettings", label: "Backup", icon: "💾" },
];

const SUPER_ADMIN_TABS = [
  { id: "superAdmin", label: "Control Center", icon: "🎛️" },
  { id: "menuVisibility", label: "Menyu", icon: "📋" },
  { id: "dashboardWidgets", label: "Dashboard", icon: "📊" },
  { id: "productionStages", label: "Bosqichlar", icon: "🏭" },
  { id: "systemLogs", label: "Jurnallar", icon: "📜" },
  { id: "mobileApp", label: "Mobil APK", icon: "📱" },
  { id: "labelPrinters", label: "Printers", icon: "🖨️" },
];

const OPERATIONS_TABS = [
  { id: "users", label: "Foydalanuvchilar", icon: "👥" },
  { id: "permissions", label: "Ruxsatlar", icon: "🔐" },
  { id: "notifications", label: "Bildirishnomalar", icon: "🔔" },
  { id: "orders", label: "Zakazlar", icon: "📋" },
  { id: "shipments", label: "Yuk arxivi", icon: "🚚" },
  { id: "search", label: "Qidiruv", icon: "🔍" },
  { id: "online", label: "Online", icon: "🟢" },
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "audit", label: "Audit", icon: "📜" },
  { id: "migration", label: "Migratsiya", icon: "🔄" },
  { id: "backup", label: "Backup fayl", icon: "🗄️" },
];

const TABS = [...CENTRAL_TABS, ...OPERATIONS_TABS];

export default function SettingsLayout({ activeTab, onTabChange, children }) {
  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="shrink-0 lg:w-56">
        <p className="mb-2 hidden text-xs font-bold uppercase tracking-wide text-[var(--brand-muted)] lg:block">
          Markaziy sozlamalar
        </p>
        <nav className="mb-4 flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
          {CENTRAL_TABS.map((tab) => (
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
        <p className="mb-2 hidden text-xs font-bold uppercase tracking-wide text-[var(--brand-muted)] lg:block">
          Super Admin
        </p>
        <nav className="mb-4 flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
          {SUPER_ADMIN_TABS.map((tab) => (
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
        <p className="mb-2 hidden text-xs font-bold uppercase tracking-wide text-[var(--brand-muted)] lg:block">
          Boshqaruv
        </p>
        <nav className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
          {OPERATIONS_TABS.map((tab) => (
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

export { TABS, CENTRAL_TABS, OPERATIONS_TABS, SUPER_ADMIN_TABS };
