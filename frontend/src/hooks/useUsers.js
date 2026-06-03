import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const REFRESH_INTERVAL_MS = 15000;

export function useUsers({ enabled = true, forLogin = false } = {}) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const mountedRef = useRef(true);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = forLogin ? await api.getLoginUsers() : await api.getUsers();
      if (mountedRef.current) {
        setUsers(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || "Foydalanuvchilarni yuklab bo'lmadi");
        setUsers([]);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [forLogin]);

  useEffect(() => {
    mountedRef.current = true;

    if (enabled) {
      fetchUsers();
      const intervalId = setInterval(fetchUsers, REFRESH_INTERVAL_MS);
      return () => {
        mountedRef.current = false;
        clearInterval(intervalId);
      };
    }

    return () => {
      mountedRef.current = false;
    };
  }, [enabled, fetchUsers]);

  const createUser = useCallback(
    async ({ username, password, role }) => {
      await api.createUser({ username, password, role });
      await fetchUsers();
    },
    [fetchUsers]
  );

  return { users, loading, error, fetchUsers, createUser };
}
