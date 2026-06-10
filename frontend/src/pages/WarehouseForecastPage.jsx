import { useEffect, useState } from "react";
import { api } from "../api/client";
import BackButton from "../components/ui/BackButton";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

const TREND_BADGE = {
  up: { label: "▲ Rising", className: "bg-red-100 text-red-700" },
  down: { label: "▼ Falling", className: "bg-green-100 text-green-700" },
  stable: { label: "→ Stable", className: "bg-blue-100 text-blue-700" },
  none: { label: "— No usage", className: "bg-gray-100 text-gray-600" },
};

function qty(value) {
  const n = Number(value || 0);
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(2);
}

export default function WarehouseForecastPage() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ window_days: 30, low_stock_threshold_days: 14 });
  const [category, setCategory] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const data = await api.warehouseForecast({
        category,
        low_stock_only: lowOnly ? "true" : "",
      });
      setItems(data.items || []);
      setMeta({
        window_days: data.window_days,
        low_stock_threshold_days: data.low_stock_threshold_days,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = window.setTimeout(load, 250);
    return () => window.clearTimeout(id);
  }, [category, lowOnly]);

  const lowCount = items.filter((i) => i.low_stock).length;

  return (
    <div className="pb-24">
      <BackButton fallback="/materials" label="Materials" className="mb-4" />
      <PageHeader
        title="Warehouse Forecast"
        subtitle={`Consumption over last ${meta.window_days} days · low stock under ${meta.low_stock_threshold_days} days`}
      />

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Materials tracked</p>
          <p className="mt-1 text-2xl font-black">{items.length}</p>
        </div>
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Low stock</p>
          <p className="mt-1 text-2xl font-black text-red-500">{lowCount}</p>
        </div>
        <div className="rounded-3xl border bg-[var(--brand-card)] p-4">
          <p className="text-xs uppercase text-[var(--brand-muted)]">Healthy</p>
          <p className="mt-1 text-2xl font-black text-green-600">{items.length - lowCount}</p>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="Filter by category (paint, profile, component...)"
          className="flex-1 rounded-xl border bg-[var(--brand-card)] px-4 py-3 text-[var(--brand-text)]"
        />
        <label className="flex items-center gap-2 text-sm font-semibold text-[var(--brand-text)]">
          <input
            type="checkbox"
            checked={lowOnly}
            onChange={(e) => setLowOnly(e.target.checked)}
            className="h-4 w-4"
          />
          Low stock only
        </label>
      </div>

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-2">
        {items.map((item) => {
          const trend = TREND_BADGE[item.trend] || TREND_BADGE.none;
          return (
            <div
              key={item.material_id}
              className={`rounded-2xl border bg-[var(--brand-card)] p-4 ${
                item.low_stock ? "border-red-300" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-bold text-[var(--brand-text)]">
                    {item.low_stock ? "⚠️ " : ""}
                    {item.name}
                  </p>
                  <p className="text-xs text-[var(--brand-muted)]">
                    {item.code ? `${item.code} · ` : ""}
                    {item.category || "No category"}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${trend.className}`}>
                  {trend.label}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div>
                  <p className="text-xs text-[var(--brand-muted)]">In stock</p>
                  <p className="font-bold">
                    {qty(item.quantity)} {item.unit}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--brand-muted)]">Used / {meta.window_days}d</p>
                  <p className="font-bold">{qty(item.consumed_30d)}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--brand-muted)]">Daily avg</p>
                  <p className="font-bold">{qty(item.avg_daily_consumption)}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--brand-muted)]">Days remaining</p>
                  <p
                    className={`font-black ${
                      item.days_remaining != null && item.days_remaining <= meta.low_stock_threshold_days
                        ? "text-red-500"
                        : "text-green-600"
                    }`}
                  >
                    {item.days_remaining != null ? `${item.days_remaining} d` : "∞"}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
        {!loading && items.length === 0 ? (
          <p className="py-12 text-center text-sm text-[var(--brand-muted)]">No materials found</p>
        ) : null}
      </div>
    </div>
  );
}
