import DashboardClock from "./DashboardClock";
import { useLocale } from "../../context/LocaleContext";

export default function StatsCards({ orders }) {
  const { t } = useLocale();
  const totalOrders = orders.length;
  const completedOrders = orders.filter((item) => item.status === "Tayyor").length;
  const activeOrders = orders.filter((item) => item.status !== "Tayyor").length;

  return (
    <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 xl:gap-6">
      <div className="brand-surface rounded-[var(--brand-radius)] bg-[var(--brand-card)] p-6 shadow-[var(--brand-shadow)]">
        <p className="text-[var(--brand-muted)]">{t("dashboardTable.totalOrders")}</p>
        <h2 className="mt-3 text-4xl font-black">{totalOrders}</h2>
      </div>

      <div
        className="brand-surface rounded-[var(--brand-radius)] p-6 text-white shadow-[var(--brand-shadow)]"
        style={{ backgroundColor: "var(--brand-success)" }}
      >
        <p>{t("dashboardTable.ready")}</p>
        <h2 className="mt-3 text-4xl font-black">{completedOrders}</h2>
      </div>

      <div
        className="brand-surface rounded-[var(--brand-radius)] p-6 text-white shadow-[var(--brand-shadow)]"
        style={{ backgroundColor: "var(--brand-warning)" }}
      >
        <p>{t("dashboardTable.inProduction")}</p>
        <h2 className="mt-3 text-4xl font-black">{activeOrders}</h2>
      </div>

      <DashboardClock />
    </div>
  );
}
