import { useEffect, useState } from "react";
import { api } from "../api/client";
import OnlineOperatorsTable from "../components/dashboard/OnlineOperatorsTable";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function OperatorsPage() {
  const [online, setOnline] = useState([]);
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [o, s] = await Promise.all([
        api.getOnlineOperators(),
        api.getOperatorStats(),
      ]);
      setOnline(o.operators || []);
      setRankings(s.operators || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  if (loading && !online.length) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader title="Operatorlar" subtitle="Online holat va samaradorlik" />
      <ErrorAlert message={error} onRetry={load} />

      <Card className="mb-6">
        <h2 className="mb-4 font-bold">Online operatorlar</h2>
        <OnlineOperatorsTable operators={online} loading={loading} />
      </Card>

      <Card>
        <h2 className="mb-4 font-bold">Reyting (tugatilgan bosqichlar)</h2>
        <div className="space-y-3">
          {rankings.map((op, i) => (
            <div
              key={op.operator}
              className="flex items-center justify-between rounded-2xl border p-4"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-black font-bold text-white">
                  {i + 1}
                </span>
                <span className="font-bold">{op.operator}</span>
              </div>
              <span className="text-green-600 font-black">{op.completed} ta</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
