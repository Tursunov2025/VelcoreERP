import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";

function StatCard({ label, value, accent }) {
  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 text-center">
      <p className="text-2xl font-black sm:text-3xl" style={{ color: accent || "var(--brand-primary)" }}>
        {value}
      </p>
      <p className="mt-1 text-xs text-[var(--brand-muted)] sm:text-sm">{label}</p>
    </div>
  );
}

export default function GpsMonitoringHubPage() {
  const { hasPermission, isAdmin } = useAuth();
  const canView = isAdmin || hasPermission("export_view");

  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.gpsDashboard();
      setStats(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">GPS Monitoring — ruxsat yo&apos;q</p>;
  }

  const links = [
    {
      to: "/gps/monitoring",
      title: "GPS Monitoring",
      desc: "Jonli xarita — barcha mashinalar (5s yangilanish)",
      emoji: "🗺️",
    },
    {
      to: "/gps/transports",
      title: "Transportlar",
      desc: "Eksport va ichki transport reyslari",
      emoji: "🚛",
    },
    {
      to: "/gps/vehicles",
      title: "Avtomobillar",
      desc: "Fleet ro&apos;yxati va davlat raqamlari",
      emoji: "🚚",
    },
    {
      to: "/gps/drivers",
      title: "Haydovchilar",
      desc: "Haydovchilar ro&apos;yxati va aloqa",
      emoji: "👤",
    },
    {
      to: "/gps/tasks",
      title: "Vazifalar",
      desc: "Transport vazifalari va GPS kuzatuv",
      emoji: "📋",
    },
    {
      to: "/driver",
      title: "Haydovchi mobil",
      desc: "GPS yuborish — login, mashina tanlash, tracking",
      emoji: "📱",
    },
  ];

  return (
    <div className="pb-24">
      <PageHeader
        title="GPS Monitoring"
        subtitle="Fleet kuzatuv — OpenStreetMap / Leaflet"
      />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      {stats ? (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          <StatCard label="Online" value={stats.online_trucks ?? 0} accent="#16a34a" />
          <StatCard label="Harakatda" value={stats.moving_vehicles ?? 0} accent="#22c55e" />
          <StatCard label="To'xtagan" value={stats.stopped_vehicles ?? 0} accent="#f59e0b" />
          <StatCard label="Jami mashina" value={stats.total_vehicles ?? 0} accent="var(--brand-primary)" />
          <StatCard label="O'rtacha tezlik" value={`${stats.average_speed_kmh ?? 0} km/h`} accent="#6366f1" />
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {links.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="rounded-2xl border bg-[var(--brand-card)] p-5 shadow-sm transition hover:border-[var(--brand-primary)]"
          >
            <span className="text-3xl">{card.emoji}</span>
            <h3 className="mt-3 text-lg font-bold">{card.title}</h3>
            <p className="mt-1 text-sm text-[var(--brand-muted)]">{card.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
