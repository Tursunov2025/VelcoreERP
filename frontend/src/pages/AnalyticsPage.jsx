import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getDashboardAnalytics());
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

  const summary = data?.summary || {};

  return (
    <div>
      <PageHeader title="Analitika" subtitle="Savdo, daromad va foyda" />
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Daromad", value: summary.total_income, color: "text-green-600" },
          { label: "Xarajat", value: summary.total_expenses, color: "text-red-600" },
          { label: "Foyda", value: summary.net_profit, color: "text-blue-600" },
          { label: "Savdo", value: summary.total_revenue, color: "text-black" },
        ].map((item) => (
          <Card key={item.label}>
            <p className="text-sm text-gray-500">{item.label}</p>
            <p className={`text-2xl font-black ${item.color}`}>
              {Number(item.value || 0).toLocaleString()} so&apos;m
            </p>
          </Card>
        ))}
      </div>

      <Card className="mb-6">
        <h2 className="mb-4 font-bold">Oylik savdo</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data?.monthly_sales || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="sales" stroke="#000" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 font-bold">Ishlab chiqarish statistikasi</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data?.production_stats || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="stage" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
