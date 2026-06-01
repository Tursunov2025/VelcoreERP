import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import DashboardClock from "../components/dashboard/DashboardClock";
import OnlineOperatorsTable from "../components/dashboard/OnlineOperatorsTable";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import PageHeader from "../components/ui/PageHeader";
import { CardSkeleton } from "../components/ui/Skeleton";
import { useLocale } from "../context/LocaleContext";

export default function DashboardPage() {
  const { t } = useLocale();
  const [analytics, setAnalytics] = useState(null);
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [a, o] = await Promise.all([
        api.getDashboardAnalytics(),
        api.getOnlineOperators(),
      ]);
      setAnalytics(a);
      setOperators(o.operators || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  const summary = analytics?.summary || {};

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading ? (
          [1, 2, 3, 4].map((i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <Card>
              <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.totalOrders")}</p>
              <p className="mt-2 text-2xl font-black">{summary.total_orders}</p>
            </Card>
            <Card>
              <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.active")}</p>
              <p className="mt-2 text-2xl font-black">{summary.active_orders}</p>
            </Card>
            <Card>
              <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.completed")}</p>
              <p className="mt-2 text-2xl font-black">{summary.completed_orders}</p>
            </Card>
            <DashboardClock />
          </>
        )}
      </div>

      <Card className="mb-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">{t("dashboard.onlineOperators")}</h2>
          <Link to="/operators" className="text-sm text-blue-600 hover:underline">
            {t("dashboard.details")}
          </Link>
        </div>
        <ErrorAlert message={error} onRetry={load} />
        <OnlineOperatorsTable operators={operators} loading={loading} />
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-bold">{t("dashboard.productionStats")}</h2>
        <div className="h-64">
          {loading ? (
            <div className="h-full animate-pulse rounded-2xl bg-gray-100" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics?.production_stats || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="stage" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="var(--brand-primary)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  );
}
