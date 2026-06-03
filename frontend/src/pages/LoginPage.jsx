import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useBranding } from "../context/BrandingContext";
import { useLocale } from "../context/LocaleContext";
import { useUsers } from "../hooks/useUsers";

const ROLE_LABELS = { admin: "Admin", operator: "Operator" };
const DEPT_LABEL = (u) => (u.department ? ` — ${u.department}` : "");

export default function LoginPage() {
  const { login, loginError, isSubmitting } = useAuth();
  const { branding, assetUrl } = useBranding();
  const { t } = useLocale();
  const { users, loading, error, fetchUsers } = useUsers({ enabled: true, forLogin: true });
  const [loginUser, setLoginUser] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    await login(loginUser, loginPassword);
  };

  const loginLogo = branding.logo_login || branding.logo_main;
  const tagline = branding.tagline || t("login.tagline");

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ backgroundColor: "var(--brand-background)" }}
    >
      <div className="brand-surface w-full max-w-md bg-[var(--brand-card)] p-8 md:p-10">
        {loginLogo ? (
          <img
            src={assetUrl(loginLogo)}
            alt={branding.app_name}
            className="mx-auto mb-4 h-16 object-contain"
          />
        ) : null}
        <h1 className="mb-2 text-center text-3xl font-black text-[var(--brand-text)] md:text-4xl">
          {branding.app_name}
        </h1>
        <p className="mb-8 text-center text-sm text-[var(--brand-muted)]">{tagline}</p>
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--brand-muted)]">
              {t("login.user")}
            </label>
            <select
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              disabled={loading}
              className="w-full rounded-[var(--brand-radius)] border bg-[var(--brand-card)] px-5 py-4 outline-none focus:ring-2 focus:ring-[var(--brand-primary)]"
            >
              <option value="">
                {loading ? t("login.loading") : t("login.userPlaceholder")}
              </option>
              {users.map((user) => (
                <option key={user.username} value={user.username}>
                  {user.username} — {ROLE_LABELS[user.role] || user.role}{DEPT_LABEL(user)}
                </option>
              ))}
            </select>
            {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--brand-muted)]">
              {t("login.password")}
            </label>
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              placeholder={t("login.passwordPlaceholder")}
              className="w-full rounded-[var(--brand-radius)] border bg-[var(--brand-card)] px-5 py-4 outline-none focus:ring-2 focus:ring-[var(--brand-primary)]"
            />
          </div>
          {loginError && <p className="text-sm text-red-500">{loginError}</p>}
          <button
            type="submit"
            disabled={isSubmitting}
            className="brand-btn w-full py-4 font-bold text-white disabled:opacity-60"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {isSubmitting ? t("login.submitting") : t("login.submit")}
          </button>
          <button
            type="button"
            onClick={fetchUsers}
            className="w-full text-sm text-[var(--brand-muted)] hover:text-[var(--brand-text)]"
          >
            {t("login.refreshUsers")}
          </button>
        </form>
      </div>
    </div>
  );
}
