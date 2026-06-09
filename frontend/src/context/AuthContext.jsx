import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getStoredTokens, setStoredTokens } from "../api/client";

const AuthContext = createContext(null);

const DEFAULT_PERMISSIONS = {
  orders: true,
  production: true,
  warehouse: false,
  tasks: true,
  finance: false,
  chat: true,
  settings: false,
  llp_view: true,
  llp_download: true,
  llp_upload: false,
  llp_edit: false,
  llp_delete: false,
  llp_read_confirm: true,
  mes_view: true,
  mes_edit: false,
  mes_delete: false,
  mes_routes_design: false,
  mes_drawings_upload: false,
  mes_jobs_view: false,
  mes_jobs_manage: false,
  mes_terminal_lazer: false,
  mes_terminal_svarshik: false,
  mes_terminal_kraska: false,
  mes_terminal_qc: false,
  mes_terminal_packaging: false,
  mes_terminal_warehouse: false,
  mes_terminal_dispatch: false,
  materials_view: false,
  materials_edit: false,
};

async function loadPermissions() {
  try {
    const data = await api.getMyPermissions();
    return data.permissions || DEFAULT_PERMISSIONS;
  } catch {
    return DEFAULT_PERMISSIONS;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [permissions, setPermissions] = useState(DEFAULT_PERMISSIONS);
  const [loading, setLoading] = useState(true);
  const [loginError, setLoginError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const tokens = getStoredTokens();
    if (!tokens?.access_token) {
      setLoading(false);
      return;
    }

    let settled = false;
    const safetyTimer = setTimeout(() => {
      if (!settled) {
        settled = true;
        setLoading(false);
      }
    }, 12_000);

    Promise.all([api.getMe(), loadPermissions()])
      .then(([data, perms]) => {
        if (settled) return;
        setUser({
          username: data.username,
          role: data.role,
          department: data.department || (data.role === "admin" ? "Admin" : "Kesish"),
          id: data.id,
        });
        setPermissions(perms);
      })
      .catch(() => setStoredTokens(null))
      .finally(() => {
        settled = true;
        clearTimeout(safetyTimer);
        setLoading(false);
      });
  }, []);

  const login = useCallback(async (username, password) => {
    setLoginError("");
    setIsSubmitting(true);
    try {
      if (!username) throw new Error("Foydalanuvchini tanlang");
      if (!password) throw new Error("Parolni kiriting");

      const data = await api.login({ username, password });
      setStoredTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        username: data.username,
        role: data.role,
        department: data.department,
      });
      setUser({
        username: data.username,
        role: data.role,
        department: data.department,
      });
      setPermissions(await loadPermissions());
    } catch (err) {
      setLoginError(err.message || "Login yoki parol xato");
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const logout = useCallback(() => {
    setStoredTokens(null);
    setUser(null);
    setPermissions(DEFAULT_PERMISSIONS);
    setLoginError("");
  }, []);

  const isAdmin = user?.role === "admin" || user?.department === "Admin";

  const hasPermission = useCallback(
    (module) => {
      if (isAdmin) return true;
      if (!module) return true;
      return Boolean(permissions?.[module]);
    },
    [isAdmin, permissions]
  );

  const value = {
    user,
    username: user?.username ?? "",
    role: user?.role ?? "",
    department: user?.department ?? "",
    permissions,
    isAdmin,
    isOmbor: user?.department === "Ombor",
    isLoggedIn: Boolean(user),
    hasPermission,
    loading,
    loginError,
    isSubmitting,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
