import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

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

export default function MaterialsHubPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [stats, setStats] = useState({
    low_stock: 0,
    receipts_today: 0,
    issues_today: 0,
    inventory_value: 0,
    shortage_count: 0,
    consumed_today: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const data = await api.materialsDashboard();
      setStats(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  const links = [
    { to: "/materials/consumed-today", title: t("materials.hubConsumedToday"), desc: t("materials.hubConsumedTodayDesc"), emoji: "📉" },
    { to: "/materials/consumption-rules", title: t("materials.hubConsumptionRules"), desc: t("materials.hubConsumptionRulesDesc"), emoji: "⚙️" },
    { to: "/materials/shortages", title: t("materials.hubShortages"), desc: t("materials.hubShortagesDesc"), emoji: "⚠️" },
    { to: "/materials/part-bom", title: t("materials.hubPartBom"), desc: t("materials.hubPartBomDesc"), emoji: "🔩" },
    { to: "/materials/items", title: t("materials.hubItems"), desc: t("materials.hubItemsDesc"), emoji: "📋" },
    { to: "/materials/categories", title: t("materials.hubCategories"), desc: t("materials.hubCategoriesDesc"), emoji: "🗂️" },
    ...(canEdit
      ? [
          { to: "/materials/receipts", title: t("materials.hubReceipts"), desc: t("materials.hubReceiptsDesc"), emoji: "📥" },
          { to: "/materials/issues", title: t("materials.hubIssues"), desc: t("materials.hubIssuesDesc"), emoji: "📤" },
          { to: "/materials/adjustments", title: t("materials.hubAdjustments"), desc: t("materials.hubAdjustmentsDesc"), emoji: "⚖️" },
        ]
      : []),
    { to: "/materials/movements", title: t("materials.hubMovements"), desc: t("materials.hubMovementsDesc"), emoji: "📊" },
  ];

  return (
    <div className="pb-24">
      <PageHeader title={t("materials.title")} subtitle={t("materials.subtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label={t("materials.consumedTodayCount")} value={stats.consumed_today ?? 0} accent="#16a34a" />
        <StatCard label={t("materials.shortageItems")} value={stats.shortage_count ?? 0} accent="#dc2626" />
        <StatCard label={t("materials.lowStock")} value={stats.low_stock} accent="#dc2626" />
        <StatCard label={t("materials.receiptsToday")} value={stats.receipts_today} accent="#16a34a" />
        <StatCard label={t("materials.issuesToday")} value={stats.issues_today} accent="#ea580c" />
        <StatCard
          label={t("materials.inventoryValue")}
          value={stats.inventory_value.toLocaleString()}
          accent="var(--brand-primary)"
        />
      </div>

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
