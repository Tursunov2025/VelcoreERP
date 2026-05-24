import Sidebar from "./Sidebar";

export default function DashboardLayout({ username, role, children }) {
  return (
    <div className="flex min-h-screen bg-[#f5f6fa]">
      <Sidebar username={username} role={role} />
      <main className="min-w-0 flex-1 p-4 md:p-6 lg:p-10">{children}</main>
    </div>
  );
}
