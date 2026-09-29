import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import {
  AdminCard,
  AdminSection,
  Notice,
  ResourceState,
  buttonClass,
  fieldClass,
  usePlatformResource,
} from "./AdminSection";
export default function SecurityTab() {
  const { t } = useLocale();
  const loader = useCallback(() => api.platformSecurity(), []);
  const state = usePlatformResource(loader);
  const [form, setForm] = useState(null);
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (state.data) setForm(state.data);
  }, [state.data]);
  if (state.loading || state.error || !form)
    return <ResourceState {...state} onRetry={state.reload} />;
  const set = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const save = async () => {
    try {
      const result = await api.platformSaveSecurity({
        ...form,
        allowed_cors_origins: String(form.allowed_cors_origins || "")
          .split(/\r?\n/)
          .map((value) => value.trim())
          .filter(Boolean),
        confirmation,
      });
      setForm({
        ...result,
        effective_cors_origins: form.effective_cors_origins,
      });
      setConfirmation("");
      setMessage(t("notifications.saved"));
    } catch (error) {
      state.setError(error.message);
    }
  };
  const origins = Array.isArray(form.allowed_cors_origins)
    ? form.allowed_cors_origins.join("\n")
    : form.allowed_cors_origins;
  return (
    <AdminSection
      title={t("platformAdministration.security")}
      description={t("platformAdministration.subtitle")}
    >
      {message ? <Notice>{message}</Notice> : null}
      <div className="grid gap-5 xl:grid-cols-2">
        <AdminCard title={t("platformAdministration.authPolicy")}>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              [t("platformAdministration.minimumPasswordLength"), "minimum_password_length"], [t("platformAdministration.loginAttemptLimit"), "login_attempt_limit"], [t("platformAdministration.lockoutMinutes"), "lockout_minutes"], [t("platformAdministration.sessionExpirationMinutes"), "session_expiration_minutes"],
            ].map(([label, key]) => (
              <label key={key}>
                <span className="mb-1 block text-sm font-bold">{label}</span>
                <input
                  className={fieldClass}
                  type="number"
                  value={form[key]}
                  onChange={(e) => set(key, Number(e.target.value))}
                />
              </label>
            ))}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.require_password_change}
                onChange={(e) =>
                  set("require_password_change", e.target.checked)
                }
              />{" "}
              {t("platformAdministration.requirePasswordChange")}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.secure_cookie_required}
                onChange={(e) =>
                  set("secure_cookie_required", e.target.checked)
                }
              />{" "}
              {t("platformAdministration.secureCookies")}
            </label>
          </div>
        </AdminCard>
        <AdminCard
          title={t("platformAdministration.allowedCors")}
          description={t("platformAdministration.subtitle")}
        >
          <textarea
            className={`${fieldClass} min-h-32`}
            value={origins}
            onChange={(e) => set("allowed_cors_origins", e.target.value)}
          />
          <p className="mt-3 text-xs text-[var(--brand-muted)]">
            {t("platformAdministration.effectiveOrigins")}: {" "}
            {(form.effective_cors_origins || []).join(", ")}
          </p>
        </AdminCard>
      </div>
      <AdminCard
        title={t("platformAdministration.activeSessions")}
        description={t("platformAdministration.subtitle")}
      >
        <div className="space-y-2">
          {(form.active_sessions || []).map((session) => (
            <div key={session.id} className="rounded-xl border p-3 text-sm">
              <strong>{session.username}</strong> ·{" "}
              {session.device || session.browser || t("platformAdministration.unknownDevice")} ·{" "}
              {session.ip_address || t("platformAdministration.unknownIp")}
            </div>
          ))}
          {!form.active_sessions?.length ? (
            <p className="text-sm text-[var(--brand-muted)]">
              {t("platformAdministration.noSessions")}
            </p>
          ) : null}
        </div>
      </AdminCard>
      <AdminCard
        title={t("platformAdministration.highRiskConfirmation")}
        description={t("platformAdministration.subtitle")}
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className={fieldClass}
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
          />
          <button
            className={buttonClass}
            disabled={confirmation !== "APPLY SECURITY POLICY"}
            onClick={save}
          >
            {t("platformAdministration.applyPolicy")}
          </button>
        </div>
      </AdminCard>
    </AdminSection>
  );
}
