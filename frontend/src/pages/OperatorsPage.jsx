import { useEffect, useState } from "react";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function OperatorsPage() {
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getOperatorStats();
      setOperators(data.operators || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader title="Operatorlar" subtitle="Samaradorlik va reyting" />
      <ErrorAlert message={error} onRetry={load} />

      <div className="space-y-4">
        {operators.map((op, index) => (
          <Card key={op.operator}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-black text-lg font-black text-white">
                  {index + 1}
                </span>
                <div>
                  <p className="text-lg font-bold">{op.operator}</p>
                  <p className="text-sm text-gray-500">
                    Samaradorlik: {op.performance}%
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <p className="font-black text-green-600">{op.completed}</p>
                  <p className="text-gray-500">Tayyor</p>
                </div>
                <div>
                  <p className="font-black text-yellow-600">{op.active}</p>
                  <p className="text-gray-500">Faol</p>
                </div>
                <div>
                  <p className="font-black">{op.total}</p>
                  <p className="text-gray-500">Jami</p>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
