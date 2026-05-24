export default function OnlineOperatorsTable({
  operators = [],
  loading,
  showLoginTime = false,
}) {
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
    return <p className="text-center text-gray-500 py-6">Operatorlar yo&apos;q</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-left text-sm">
        <thead>
          <tr className="border-b text-gray-500">
            <th className="py-3 pr-4">Operator</th>
            <th className="py-3 pr-4">Bo&apos;lim</th>
            <th className="py-3 pr-4">Holat</th>
            <th className="py-3 pr-4">Faol zakazlar</th>
            {showLoginTime && <th className="py-3 pr-4">Kirish vaqti</th>}
            <th className="py-3">Oxirgi faollik</th>
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
                  {op.is_online ? "Online" : "Offline"}
                </span>
              </td>
              <td className="py-3 font-bold">{op.active_orders_count}</td>
              {showLoginTime && (
                <td className="py-3 text-xs text-gray-500">
                  {op.login_at ? new Date(op.login_at).toLocaleString() : "—"}
                </td>
              )}
              <td className="py-3 text-gray-500 text-xs">
                {op.last_activity
                  ? new Date(op.last_activity).toLocaleString()
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
