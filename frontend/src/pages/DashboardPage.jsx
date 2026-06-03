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
import { isWidgetEnabled } from "../constants/controlCenter";
import { useAuth } from "../context/AuthContext";
import { useLocale } from "../context/LocaleContext";
import { useUiConfig } from "../hooks/useUiConfig";

export default function DashboardPage() {
  const { t } = useLocale();
  const { isAdmin } = useAuth();
  const { config } = useUiConfig();
  const widgets = config?.dashboard_widgets || [];
  const [analytics, setAnalytics] = useState(null);
  const [operators, setOperators] = useState([]);
  const [delayedCount, setDelayedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const tasks = [api.getOnlineOperators()];
      if (isWidgetEnabled(widgets, "order_stats") || isWidgetEnabled(widgets, "production_chart")) {
        tasks.push(
          api.getDashboardAnalytics().catch(() => null)
        );
      }
      if (isAdmin && isWidgetEnabled(widgets, "delayed_summary")) {
        tasks.push(
          api.controlCenterOrders({ delayed_only: true, limit: 200 }).catch(() => ({ summary: {} }))
        );
      }
      const results = await Promise.all(tasks);
      setOperators(results[0]?.operators || []);
      let idx = 1;
      if (isWidgetEnabled(widgets, "order_stats") || isWidgetEnabled(widgets, "production_chart")) {
        setAnalytics(results[idx] || null);
        idx += 1;
      }
      if (isAdmin && isWidgetEnabled(widgets, "delayed_summary") && results[idx]) {
        setDelayedCount(results[idx]?.summary?.delayed ?? 0);
      }
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
  }, [isAdmin, widgets.length]);

  const summary = analytics?.summary || {};

  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />

      {isAdmin && isWidgetEnabled(widgets, "delayed_summary") && delayedCount > 0 ? (
        <Link
          to="/control-center"
          className="mb-4 block rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800"
        >
          {t("controlCenter.delayedAlert")} ({delayedCount})
        </Link>
      ) : null}

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading ? (
          [1, 2, 3, 4].map((i) => <CardSkeleton key={i} />)
        ) : (
          <>
            {isWidgetEnabled(widgets, "order_stats") ? (
              <>
                <Card>
                  <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.totalOrders")}</p>
                  <p className="mt-2 text-2xl font-black">{summary.total_orders ?? "—"}</p>
                </Card>
                <Card>
                  <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.active")}</p>
                  <p className="mt-2 text-2xl font-black">{summary.active_orders ?? "—"}</p>
                </Card>
                <Card>
                  <p className="text-sm text-[var(--brand-muted)]">{t("dashboard.completed")}</p>
                  <p className="mt-2 text-2xl font-black">{summary.completed_orders ?? "—"}</p>
                </Card>
              </>
            ) : null}
            {isWidgetEnabled(widgets, "clock") ? <DashboardClock /> : null}
          </>
        )}
      </div>

      {isWidgetEnabled(widgets, "online_operators") ? (
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
      ) : null}

      {isWidgetEnabled(widgets, "production_chart") ? (
        <Card>
          <h2 className="mb-4 text-lg font-bold">{t("dashboard.productionStats")}</h2>
          <div className="h-64">
            {loading ? (
              <div className="h-full animate-pulse rounded-2xl bg-gray-100" />
            ) : analytics?.production_stats?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.production_stats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="stage" tick={{ fontSize: 10 }} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--brand-primary)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-12 text-center text-sm text-[var(--brand-muted)]">
                {t("dashboard.noChartData")}
              </p>
            )}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
