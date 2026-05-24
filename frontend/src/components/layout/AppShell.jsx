import { useAuth } from "../../context/AuthContext";
import MobileNav from "./MobileNav";
import Sidebar from "./Sidebar";

export default function AppShell({ children }) {
  const { username, role, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-[#f5f6fa]">
      <Sidebar username={username} role={role} />
      <div className="flex min-w-0 flex-1 flex-col pb-24 md:pb-0">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-white/90 px-4 py-3 backdrop-blur md:hidden">
          <div>
            <p className="text-xs text-gray-500">Azmus ERP</p>
            <p className="font-bold">{username}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="rounded-xl bg-red-500 px-4 py-2 text-sm text-white"
          >
            Chiqish
          </button>
        </header>
        <main className="flex-1 p-4 md:p-8">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
