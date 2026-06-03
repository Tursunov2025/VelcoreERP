import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

export default function SystemLogsTab() {
  const { t } = useLocale();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [username, setUsername] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.adminGetAuditLogs({
        limit: 300,
        q,
        action,
        entity_type: entityType,
        username,
      });
      setLogs(Array.isArray(data) ? data : data.logs || []);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [q, action, entityType, username]);

  useEffect(() => {
    const timer = window.setTimeout(load, 300);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div>
      <h2 className="mb-2 text-xl font-black">{t("controlCenter.logsTitle")}</h2>
      <p className="mb-4 text-sm text-[var(--brand-muted)]">{t("controlCenter.logsSubtitle")}</p>

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("controlCenter.logSearch")}
          className="min-h-[44px] rounded-xl border px-3"
        />
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder={t("controlCenter.logUser")}
          className="min-h-[44px] rounded-xl border px-3"
        />
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder={t("controlCenter.logAction")}
          className="min-h-[44px] rounded-xl border px-3"
        />
        <input
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          placeholder={t("controlCenter.logEntity")}
          className="min-h-[44px] rounded-xl border px-3"
        />
      </div>

      {loading ? (
        <p>{t("common.loading")}</p>
      ) : (
        <div className="max-h-[65vh] space-y-2 overflow-y-auto rounded-2xl border bg-white p-2">
          {logs.length === 0 ? (
            <p className="py-8 text-center text-gray-500">{t("controlCenter.logsEmpty")}</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="rounded-xl border px-3 py-2 text-sm">
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
                  {log.entity_id != null ? ` #${log.entity_id}` : ""}
                </p>
                {log.details ? <p className="mt-1 text-gray-500">{log.details}</p> : null}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
