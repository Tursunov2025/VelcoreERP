import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getStoredTokens, setStoredTokens } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loginError, setLoginError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const tokens = getStoredTokens();
    if (!tokens?.access_token) {
      setLoading(false);
      return;
    }

    api
      .getMe()
      .then((data) => {
        setUser({
          username: data.username,
          role: data.role,
          department: data.department,
          id: data.id,
        });
      })
      .catch(() => setStoredTokens(null))
      .finally(() => setLoading(false));
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
    } catch (err) {
      setLoginError(err.message || "Login yoki parol xato");
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const logout = useCallback(() => {
    setStoredTokens(null);
    setUser(null);
    setLoginError("");
  }, []);

  const value = {
    user,
    username: user?.username ?? "",
    role: user?.role ?? "",
    department: user?.department ?? "",
    isAdmin: user?.role === "admin" || user?.department === "Admin",
    isOmbor: user?.department === "Ombor",
    isLoggedIn: Boolean(user),
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
