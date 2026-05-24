import { useEffect, useState } from "react";
import { api } from "../../api/client";
import OnlineOperatorsTable from "../dashboard/OnlineOperatorsTable";

export default function OnlineTab() {
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.adminGetOnlineUsers();
      setOperators(data.operators || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-black">Online operatorlar</h2>
        <button
          type="button"
          onClick={load}
          className="rounded-xl border px-4 py-2 text-sm"
        >
          Yangilash
        </button>
      </div>
      <div className="rounded-2xl border bg-white p-4">
        <OnlineOperatorsTable
          operators={operators}
          loading={loading}
          showLoginTime
        />
        <p className="mt-4 text-xs text-gray-400">
          Login vaqti va oxirgi faollik real vaqtda yangilanadi
        </p>
      </div>
    </div>
  );
}
