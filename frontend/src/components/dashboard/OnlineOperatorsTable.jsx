import { useLocale } from "../../context/LocaleContext";
export default function OnlineOperatorsTable({
  operators = [],
  loading,
  showLoginTime = false,
}) {
  const { t, formatDate } = useLocale();
  if (loading) {
    return (
      <div className="animate-pulse space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded-xl bg-gray-200" />
        ))}
      </div>
    );
  }

  if (!operators.length) {
    return <p className="text-center text-gray-500 py-6">{t("dashboardTable.noOperators")}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-left text-sm">
        <thead>
          <tr className="border-b text-gray-500">
            <th className="py-3 pr-4">{t("dashboardTable.operator")}</th><th className="py-3 pr-4">{t("dashboardTable.department")}</th><th className="py-3 pr-4">{t("common.status")}</th><th className="py-3 pr-4">{t("dashboardTable.activeOrders")}</th>
            {showLoginTime && <th className="py-3 pr-4">{t("dashboardTable.loginTime")}</th>}<th className="py-3">{t("dashboardTable.lastActivity")}</th>
          </tr>
        </thead>
        <tbody>
          {operators.map((op) => (
            <tr key={op.username} className="border-b border-gray-50">
              <td className="py-3 font-semibold">{op.username}</td>
              <td className="py-3">{op.department}</td>
              <td className="py-3">
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold ${
                    op.is_online
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      op.is_online ? "bg-green-500 animate-pulse" : "bg-gray-400"
                    }`}
                  />
                  {t(op.is_online ? "common.online" : "common.offline")}
                </span>
              </td>
              <td className="py-3 font-bold">{op.active_orders_count}</td>
              {showLoginTime && (
                <td className="py-3 text-xs text-gray-500">
                  {op.login_at ? formatDate(op.login_at, { dateStyle: "short", timeStyle: "short" }) : "—"}
                </td>
              )}
              <td className="py-3 text-gray-500 text-xs">
                {op.last_activity
                  ? formatDate(op.last_activity, { dateStyle: "short", timeStyle: "short" })
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
