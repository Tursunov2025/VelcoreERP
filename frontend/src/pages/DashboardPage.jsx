import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import OnlineOperatorsTable from "../components/dashboard/OnlineOperatorsTable";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import PageHeader from "../components/ui/PageHeader";
import { CardSkeleton } from "../components/ui/Skeleton";

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState(null);
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [a, o] = await Promise.all([
        api.getDashboardAnalytics(),
        api.getOnlineOperators(),
      ]);
      setAnalytics(a);
      setOperators(o.operators || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  const summary = analytics?.summary || {};

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="ERP boshqaruv paneli" />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {loading
          ? [1, 2, 3, 4].map((i) => <CardSkeleton key={i} />)
          : [
              { label: "Jami zakaz", value: summary.total_orders },
              { label: "Faol", value: summary.active_orders },
              { label: "Tayyor", value: summary.completed_orders },
              { label: "Sof foyda", value: `${Number(summary.net_profit || 0).toLocaleString()} so'm` },
            ].map((item) => (
              <Card key={item.label}>
                <p className="text-sm text-gray-500">{item.label}</p>
                <p className="mt-2 text-2xl font-black">{item.value}</p>
              </Card>
            ))}
      </div>

      <Card className="mb-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">Online operatorlar</h2>
          <Link to="/operators" className="text-sm text-blue-600 hover:underline">
            Batafsil
          </Link>
        </div>
        <ErrorAlert message={error} onRetry={load} />
        <OnlineOperatorsTable operators={operators} loading={loading} />
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-bold">Ishlab chiqarish statistikasi</h2>
        <div className="h-64">
          {loading ? (
            <div className="h-full animate-pulse rounded-2xl bg-gray-100" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics?.production_stats || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="stage" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#000" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  );
}
