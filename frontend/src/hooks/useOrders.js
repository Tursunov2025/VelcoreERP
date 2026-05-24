import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

export function useOrders({ enabled = true } = {}) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchOrders = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError("");

    try {
      const data = await api.getOrders();
      setOrders(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Zakazlarni yuklab bo'lmadi");
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const addOrder = useCallback(async ({ client, phone, amount }) => {
    const data = await api.createOrder({ client, phone, amount });
    setOrders((prev) => [...prev, data]);
    return data;
  }, []);

  const updateOrderStatus = useCallback(async (orderId, status) => {
    setOrders((prev) =>
      prev.map((order) =>
        order.id === orderId ? { ...order, status } : order
      )
    );

    try {
      await api.updateOrderStatus(orderId, status);
    } catch (err) {
      await fetchOrders();
      throw err;
    }
  }, [fetchOrders]);

  const deleteOrder = useCallback(async (orderId) => {
    await api.deleteOrder(orderId);
    setOrders((prev) => prev.filter((order) => order.id !== orderId));
  }, []);

  return {
    orders,
    loading,
    error,
    fetchOrders,
    addOrder,
    updateOrderStatus,
    deleteOrder,
  };
}
