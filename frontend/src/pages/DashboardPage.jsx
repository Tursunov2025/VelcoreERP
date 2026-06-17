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
import { useFeatureFlags } from "../hooks/useFeatureFlags";

const KPI_CARDS = [
  { key: "orders", label: "Orders", emoji: "📦", to: "/orders" },
  { key: "production_jobs", label: "Production Jobs", emoji: "🏭", to: "/mes/jobs" },
  { key: "finished_products", label: "Finished Products", emoji: "✅", to: "/mes/terminal/warehouse" },
  { key: "shipped_orders", label: "Shipped Orders", emoji: "🚚", to: "/shipping" },
  { key: "customers", label: "Customers", emoji: "👥", to: "/crm" },
  { key: "materials", label: "Materials", emoji: "🧱", to: "/materials" },
  { key: "llp_documents", label: "LLP Documents", emoji: "📄", to: "/llp" },
  { key: "export_shipments", label: "Export Shipments", emoji: "🌍", to: "/export-shipments" },
];

const QUICK_ACTIONS = [
  { label: "New Order", emoji: "➕", to: "/orders" },
  { label: "New Job", emoji: "🛠️", to: "/mes/jobs/new" },
  { label: "Material Receipt", emoji: "📥", to: "/materials/receipts" },
  { label: "Export Shipment", emoji: "🚚", to: "/export-shipments" },
  { label: "Reports", emoji: "📊", to: "/analytics" },
];

function formatNumber(value) {
  const n = Number(value || 0);
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
}

export default function DashboardPage() {
  const { t } = useLocale();
  const { isAdmin } = useAuth();
  const { config } = useUiConfig();
  const { traceabilityEnabled } = useFeatureFlags();
  const widgets = config?.dashboard_widgets || [];
  const [kpis, setKpis] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [operators, setOperators] = useState([]);
  const [delayedCount, setDelayedCount] = useState(0);
  const [traceStats, setTraceStats] = useState(null);
  const [exportStats, setExportStats] = useState(null);
  const [currencyStats, setCurrencyStats] = useState(null);
  const [topDebtors, setTopDebtors] = useState(null);
  const [forecastAlerts, setForecastAlerts] = useState(null);
  const [gpsStats, setGpsStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const [
        kpiData,
        operatorData,
        analyticsData,
        currencyData,
        debtorData,
        forecastData,
        exportData,
        gpsData,
      ] = await Promise.all([
        api.dashboardKpis().catch(() => null),
        api.getOnlineOperators().catch(() => null),
        api.getDashboardAnalytics().catch(() => null),
        api.currencyDashboard().catch(() => null),
        api.crmTopDebtors(5).catch(() => null),
        api.warehouseForecastAlerts(6).catch(() => null),
        isWidgetEnabled(widgets, "export_shipments")
          ? api.exportShipmentDashboard().catch(() => null)
          : Promise.resolve(null),
        api.gpsDashboard().catch(() => null),
      ]);
      setKpis(kpiData);
      setOperators(operatorData?.operators || []);
      setAnalytics(analyticsData);
      setCurrencyStats(currencyData);
      setTopDebtors(debtorData);
      setForecastAlerts(forecastData);
      setExportStats(exportData);
      setGpsStats(gpsData);
      if (isAdmin && isWidgetEnabled(widgets, "delayed_summary")) {
        const delayed = await api
          .controlCenterOrders({ delayed_only: true, limit: 200 })
          .catch(() => ({ summary: {} }));
        setDelayedCount(delayed?.summary?.delayed ?? 0);
      }
      if (isAdmin && traceabilityEnabled) {
        setTraceStats(await api.traceabilityDashboard().catch(() => null));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [isAdmin, traceabilityEnabled, widgets.length]);

  useEffect(() => {
    const refreshGps = async () => {
      try {
        const gpsData = await api.gpsDashboard();
        setGpsStats(gpsData);
      } catch {
        /* keep last stats */
      }
    };
    refreshGps();
    const id = setInterval(refreshGps, 5000);
    return () => clearInterval(id);
  }, []);

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

      {/* Quick Actions */}
      <div className="mb-6 flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => (
          <Link
            key={action.label}
            to={action.to}
            className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            <span>{action.emoji}</span>
            {action.label}
          </Link>
        ))}
      </div>

      {/* KPI cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {loading && !kpis
          ? [1, 2, 3, 4, 5, 6, 7, 8].map((i) => <CardSkeleton key={i} />)
          : KPI_CARDS.map((card) => (
              <Link
                key={card.key}
                to={card.to}
                className="rounded-3xl border bg-[var(--brand-card)] p-4 shadow-sm transition hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--brand-muted)]">
                    {card.label}
                  </p>
                  <span className="text-lg">{card.emoji}</span>
                </div>
                <p className="mt-2 text-3xl font-black text-[var(--brand-text)]">
                  {kpis ? formatNumber(kpis[card.key]) : "—"}
                </p>
              </Link>
            ))}
      </div>

      {isAdmin && traceabilityEnabled && traceStats ? (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Card>
            <p className="text-sm text-[var(--brand-muted)]">{t("traceability.packagesToday")}</p>
            <p className="mt-2 text-2xl font-black">{traceStats.packages_today ?? 0}</p>
          </Card>
          <Card>
            <p className="text-sm text-[var(--brand-muted)]">{t("traceability.printedToday")}</p>
            <p className="mt-2 text-2xl font-black">{traceStats.printed_labels_today ?? 0}</p>
          </Card>
          <Card>
            <p className="text-sm text-[var(--brand-muted)]">{t("traceability.inWarehouse")}</p>
            <p className="mt-2 text-2xl font-black">{traceStats.packages_in_warehouse ?? 0}</p>
          </Card>
          <Card>
            <p className="text-sm text-[var(--brand-muted)]">{t("traceability.dispatchedToday")}</p>
            <p className="mt-2 text-2xl font-black">{traceStats.packages_dispatched_today ?? 0}</p>
          </Card>
        </div>
      ) : null}

      {/* Currency / Debtors / Forecast widget row */}
      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        {currencyStats?.rates?.length ? (
          <Link
            to="/currencies"
            className="rounded-3xl border bg-[var(--brand-card)] p-5 shadow-sm transition hover:shadow-md"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-bold text-[var(--brand-text)]">💱 Exchange Rates</h2>
              <span className="text-xs text-[var(--brand-muted)]">1 unit → UZS</span>
            </div>
            <div className="space-y-2">
              {currencyStats.rates.map((rate) => {
                const delta =
                  rate.rate_to_base != null && rate.previous_rate != null
                    ? rate.rate_to_base - rate.previous_rate
                    : null;
                return (
                  <div key={rate.code} className="flex items-center justify-between text-sm">
                    <span className="font-mono font-bold text-[var(--brand-text)]">
                      {rate.code} {rate.symbol}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="font-bold text-[var(--brand-text)]">
                        {rate.rate_to_base != null ? rate.rate_to_base.toLocaleString() : "—"}
                      </span>
                      {delta != null && delta !== 0 ? (
                        <span className={delta > 0 ? "text-green-600" : "text-red-500"}>
                          {delta > 0 ? "▲" : "▼"}
                        </span>
                      ) : null}
                    </span>
                  </div>
                );
              })}
            </div>
          </Link>
        ) : null}

        {topDebtors?.debtors ? (
          <Link
            to="/crm"
            className="rounded-3xl border bg-[var(--brand-card)] p-5 shadow-sm transition hover:shadow-md"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-bold text-[var(--brand-text)]">💸 Top Debtors</h2>
              <span className="text-xs text-[var(--brand-muted)]">UZS</span>
            </div>
            {topDebtors.debtors.length === 0 ? (
              <p className="text-sm text-[var(--brand-muted)]">No outstanding debt</p>
            ) : (
              <div className="space-y-2">
                {topDebtors.debtors.map((debtor) => (
                  <div key={debtor.customer} className="flex items-center justify-between text-sm">
                    <span className="truncate font-semibold text-[var(--brand-text)]">
                      {debtor.customer}
                    </span>
                    <span className="font-bold text-red-500">
                      {debtor.outstanding_debt.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Link>
        ) : null}

        {forecastAlerts ? (
          <Link
            to="/materials/forecast"
            className="rounded-3xl border bg-[var(--brand-card)] p-5 shadow-sm transition hover:shadow-md"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-bold text-[var(--brand-text)]">📉 Low Stock Alerts</h2>
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-600">
                {forecastAlerts.total_low_stock ?? 0}
              </span>
            </div>
            {!forecastAlerts.alerts?.length ? (
              <p className="text-sm text-[var(--brand-muted)]">No low stock materials</p>
            ) : (
              <div className="space-y-2">
                {forecastAlerts.alerts.map((alert) => (
                  <div key={alert.material_id} className="flex items-center justify-between text-sm">
                    <span className="truncate font-semibold text-[var(--brand-text)]">
                      {alert.name}
                    </span>
                    <span className="text-xs font-bold text-amber-600">
                      {alert.days_remaining != null
                        ? `${alert.days_remaining}d left`
                        : `${formatNumber(alert.quantity)} ${alert.unit}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Link>
        ) : null}
      </div>

      {gpsStats ? (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Link
            to="/transport/live-map"
            className="rounded-3xl border bg-[var(--brand-card)] p-4 shadow-sm transition hover:shadow-md"
          >
            <p className="text-xs uppercase text-[var(--brand-muted)]">🚚 Online</p>
            <p className="mt-1 text-2xl font-black text-green-600">
              {gpsStats.online_trucks ?? 0}
              <span className="text-sm font-normal text-[var(--brand-muted)]">
                {" "}
                / {gpsStats.total_vehicles ?? 0}
              </span>
            </p>
          </Link>
          <Link
            to="/transport/live-map"
            className="rounded-3xl border bg-[var(--brand-card)] p-4 shadow-sm transition hover:shadow-md"
          >
            <p className="text-xs uppercase text-[var(--brand-muted)]">🟢 Moving</p>
            <p className="mt-1 text-2xl font-black text-green-600">
              {gpsStats.moving_vehicles ?? 0}
            </p>
          </Link>
          <Link
            to="/transport/live-map"
            className="rounded-3xl border bg-[var(--brand-card)] p-4 shadow-sm transition hover:shadow-md"
          >
            <p className="text-xs uppercase text-[var(--brand-muted)]">🅿️ Stopped</p>
            <p className="mt-1 text-2xl font-black text-amber-600">
              {gpsStats.stopped_vehicles ?? 0}
            </p>
          </Link>
          <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
            <p className="text-xs uppercase text-[var(--brand-muted)]">⚡ Avg Speed</p>
            <p className="mt-1 text-2xl font-black">{gpsStats.average_speed_kmh ?? 0} km/h</p>
          </div>
          <Link
            to="/transport"
            className="rounded-3xl border bg-[var(--brand-card)] p-4 shadow-sm transition hover:shadow-md"
          >
            <p className="text-xs uppercase text-[var(--brand-muted)]">🕒 ETA Arrivals</p>
            {!gpsStats.eta_arrivals?.length ? (
              <p className="mt-1 text-sm text-[var(--brand-muted)]">No active trips</p>
            ) : (
              <div className="mt-1 space-y-1">
                {gpsStats.eta_arrivals.slice(0, 2).map((row) => (
                  <p key={row.trip_id} className="truncate text-xs font-semibold">
                    {row.plate_number} → {row.destination || "—"}
                    {row.eta_hours != null ? ` (~${row.eta_hours}h)` : ""}
                  </p>
                ))}
              </div>
            )}
          </Link>
        </div>
      ) : null}

      {isWidgetEnabled(widgets, "export_shipments") && exportStats ? (
        <Link
          to="/export-shipments"
          className="mb-6 grid gap-4 rounded-3xl border bg-[var(--brand-card)] p-5 shadow-sm transition hover:shadow-md sm:grid-cols-4"
        >
          <div>
            <p className="text-sm text-[var(--brand-muted)]">Export Shipments</p>
            <p className="mt-2 text-2xl font-black">{exportStats.total ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--brand-muted)]">Ready</p>
            <p className="mt-2 text-xl font-black text-blue-600">{exportStats.ready ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--brand-muted)]">Sent</p>
            <p className="mt-2 text-xl font-black text-amber-600">{exportStats.sent ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--brand-muted)]">Delivered</p>
            <p className="mt-2 text-xl font-black text-green-600">{exportStats.delivered ?? 0}</p>
          </div>
        </Link>
      ) : null}

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        {isWidgetEnabled(widgets, "clock") ? <DashboardClock /> : null}
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
