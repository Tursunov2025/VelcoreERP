import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

const AUTH_KEY = "azmus_auth";

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function useAuth() {
  const stored = loadStoredAuth();
  const [user, setUser] = useState(stored);
  const [loginError, setLoginError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isLoggedIn = Boolean(user);
  const role = user?.role ?? "";
  const username = user?.username ?? "";
  const isAdmin = role === "admin";

  useEffect(() => {
    if (user) {
      localStorage.setItem(AUTH_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_KEY);
    }
  }, [user]);

  const login = useCallback(async (loginUsername, password) => {
    setLoginError("");
    setIsSubmitting(true);

    try {
      if (!loginUsername) {
        throw new Error("Foydalanuvchini tanlang");
      }
      if (!password) {
        throw new Error("Parolni kiriting");
      }

      const data = await api.login({ username: loginUsername, password });

      if (!data.success) {
        throw new Error("Login yoki parol xato");
      }

      setUser({
        username: data.username,
        role: data.role,
      });
    } catch (error) {
      setLoginError(error.message || "Login yoki parol xato");
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setLoginError("");
  }, []);

  return {
    user,
    username,
    role,
    isAdmin,
    isLoggedIn,
    loginError,
    isSubmitting,
    login,
    logout,
  };
}
