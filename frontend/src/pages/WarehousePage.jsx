import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Card from "../components/ui/Card";
import ErrorAlert from "../components/ui/ErrorAlert";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";

export default function WarehousePage() {
  const { isAdmin } = useAuth();
  const [materials, setMaterials] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    unit: "dona",
    quantity: 0,
    min_quantity: 5,
  });
  const [movement, setMovement] = useState({
    material_id: "",
    movement_type: "in",
    quantity: 1,
    note: "",
  });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [m, a, h] = await Promise.all([
        api.getMaterials(),
        api.getStockAlerts(),
        api.getStockHistory(),
      ]);
      setMaterials(m);
      setAlerts(a);
      setHistory(h);
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
      <PageHeader title="Ombor" subtitle="Materiallar va qoldiq boshqaruvi" />
      <ErrorAlert message={error} onRetry={load} />

      {alerts.length > 0 && (
        <Card className="mb-6 border-2 border-red-200 bg-red-50">
          <h2 className="mb-3 font-bold text-red-700">Kam qolgan materiallar</h2>
          <div className="space-y-2">
            {alerts.map((m) => (
              <p key={m.id} className="text-sm">
                {m.name}: {m.quantity} {m.unit} (min: {m.min_quantity})
              </p>
            ))}
          </div>
        </Card>
      )}

      {isAdmin && (
        <Card className="mb-6">
          <h2 className="mb-4 font-bold">Yangi material</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              placeholder="Nomi"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded-2xl border px-4 py-3"
            />
            <input
              placeholder="Birlik"
              value={form.unit}
              onChange={(e) => setForm({ ...form, unit: e.target.value })}
              className="rounded-2xl border px-4 py-3"
            />
            <input
              type="number"
              placeholder="Miqdor"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: +e.target.value })}
              className="rounded-2xl border px-4 py-3"
            />
            <input
              type="number"
              placeholder="Min qoldiq"
              value={form.min_quantity}
              onChange={(e) => setForm({ ...form, min_quantity: +e.target.value })}
              className="rounded-2xl border px-4 py-3"
            />
          </div>
          <button
            type="button"
            onClick={async () => {
              await api.createMaterial(form);
              setForm({ name: "", unit: "dona", quantity: 0, min_quantity: 5 });
              load();
            }}
            className="mt-4 rounded-2xl bg-black px-6 py-3 text-white"
          >
            Saqlash
          </button>
        </Card>
      )}

      <Card className="mb-6">
        <h2 className="mb-4 font-bold">Kirim / Chiqim</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <select
            value={movement.material_id}
            onChange={(e) => setMovement({ ...movement, material_id: e.target.value })}
            className="rounded-2xl border px-4 py-3"
          >
            <option value="">Material tanlang</option>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <select
            value={movement.movement_type}
            onChange={(e) => setMovement({ ...movement, movement_type: e.target.value })}
            className="rounded-2xl border px-4 py-3"
          >
            <option value="in">Kirim</option>
            <option value="out">Chiqim</option>
          </select>
          <input
            type="number"
            value={movement.quantity}
            onChange={(e) => setMovement({ ...movement, quantity: +e.target.value })}
            className="rounded-2xl border px-4 py-3"
          />
          <input
            placeholder="Izoh"
            value={movement.note}
            onChange={(e) => setMovement({ ...movement, note: e.target.value })}
            className="rounded-2xl border px-4 py-3"
          />
        </div>
        <button
          type="button"
          onClick={async () => {
            await api.stockMovement({
              ...movement,
              material_id: Number(movement.material_id),
            });
            load();
          }}
          className="mt-4 rounded-2xl bg-blue-600 px-6 py-3 text-white"
        >
          Amalga oshirish
        </button>
      </Card>

      <Card className="mb-6">
        <h2 className="mb-4 font-bold">Qoldiq</h2>
        <div className="space-y-3">
          {materials.map((m) => (
            <div
              key={m.id}
              className={`flex justify-between rounded-2xl border p-4 ${
                m.low_stock ? "border-red-300 bg-red-50" : ""
              }`}
            >
              <div>
                <p className="font-bold">{m.name}</p>
                <p className="text-sm text-gray-500">{m.unit}</p>
              </div>
              <p className="text-xl font-black">{m.quantity}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 font-bold">Tarix</h2>
        <div className="max-h-80 space-y-2 overflow-y-auto">
          {history.map((h) => (
            <div key={h.id} className="rounded-xl border p-3 text-sm">
              <span className="font-bold">{h.movement_type === "in" ? "+" : "-"}</span>
              {h.quantity} — material #{h.material_id} ({h.created_by})
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
