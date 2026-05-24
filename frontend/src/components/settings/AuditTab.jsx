import { useEffect, useState } from "react";
import { api } from "../../api/client";

export default function AuditTab() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .adminGetAuditLogs()
      .then(setLogs)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Yuklanmoqda...</p>;

  return (
    <div>
      <h2 className="mb-4 text-xl font-black">Audit jurnali</h2>
      <div className="max-h-[60vh] space-y-2 overflow-y-auto">
        {logs.map((log) => (
          <div key={log.id} className="rounded-xl border bg-white p-3 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-bold">{log.username}</span>
              <span className="text-xs text-gray-400">
                {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
              </span>
            </div>
            <p className="mt-1">
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-semibold">
                {log.action}
              </span>{" "}
              {log.entity_type}
              {log.entity_id != null && ` #${log.entity_id}`}
            </p>
            {log.details && <p className="mt-1 text-gray-500">{log.details}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
