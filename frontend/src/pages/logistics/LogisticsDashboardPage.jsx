import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";

const LINKS = [
  { to: "/logistics/finished-warehouse", label: "Tayyor Mahsulot Ombori", emoji: "📦" },
  { to: "/logistics/loading-plans", label: "Yuklash Rejalari", emoji: "📋" },
  { to: "/logistics/transports", label: "Transportlar", emoji: "🚛" },
  { to: "/logistics/drivers", label: "Haydovchilar", emoji: "👤" },
  { to: "/logistics/gps", label: "GPS Monitoring", emoji: "🛰️" },
  { to: "/logistics/loading-control", label: "Yuklash Nazorati", emoji: "📷" },
  { to: "/logistics/in-transit", label: "Yo'ldagi Yuklar", emoji: "🛣️" },
  { to: "/logistics/delivered", label: "Yetkazib Berilgan", emoji: "✅" },
  { to: "/logistics/live-map", label: "Jonli Xarita", emoji: "🗺️" },
  { to: "/logistics/llp", label: "LLP Hujjatlar", emoji: "📄" },
];

export default function LogisticsDashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .logisticsDashboard()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  const p = stats?.finished_products || {};
  const s = stats?.shipments || {};

  return (
    <div>
      <PageHeader title="Logistika Dashboard" subtitle="Tayyor mahsulot, yuklash va GPS" />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Available" value={p.available ?? p.ready ?? 0} />
        <StatCard label="Reserved" value={p.reserved ?? p.loading ?? 0} />
        <StatCard label="Yo'ldagi yuklar" value={s.in_transit ?? 0} />
        <StatCard label="Yetkazilgan" value={s.delivered ?? 0} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {LINKS.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            className="rounded-2xl border bg-[var(--brand-card)] p-4 font-semibold hover:shadow-md"
          >
            {l.emoji} {l.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
      <p className="text-xs uppercase text-[var(--brand-muted)]">{label}</p>
      <p className="text-2xl font-black">{value}</p>
    </div>
  );
}
