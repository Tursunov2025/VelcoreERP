import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import KanbanBoard from "../components/workflow/KanbanBoard";
import ErrorAlert from "../components/ui/ErrorAlert";
import PageHeader from "../components/ui/PageHeader";
import { useAuth } from "../context/AuthContext";
import { useLocale } from "../context/LocaleContext";

export default function ProductionPage() {
  const { department, isAdmin } = useAuth();
  const { t } = useLocale();
  const [board, setBoard] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBoard(await api.getKanban());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const handleComplete = async (orderId, body) => {
    await api.completeOrder(orderId, body);
    await load();
  };

  const handleVerify = async (orderId, body) => {
    await api.verifyOrder(orderId, body);
    await load();
  };

  return (
    <div>
      <PageHeader
        title={t("production.title")}
        subtitle={t("production.subtitle")}
        actions={
          <button
            type="button"
            onClick={load}
            className="rounded-2xl bg-black px-5 py-2 text-sm text-white"
          >
            Yangilash
          </button>
        }
      />
      <ErrorAlert message={error} onRetry={load} />
      <KanbanBoard
        board={board}
        loading={loading}
        onComplete={handleComplete}
        onVerify={handleVerify}
        onRefresh={load}
      />
    </div>
  );
}
