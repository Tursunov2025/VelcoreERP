import { useCallback, useEffect, useState } from "react";
import { useLocale } from "../../context/LocaleContext";

export const fieldClass =
  "w-full rounded-xl border border-[var(--brand-muted)]/30 bg-transparent px-3 py-2.5 text-sm text-[var(--brand-text)] outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary)]/20 disabled:opacity-60";
export const buttonClass =
  "rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50";
export const secondaryButtonClass =
  "rounded-xl border border-[var(--brand-muted)]/30 px-4 py-2.5 text-sm font-bold text-[var(--brand-text)] disabled:opacity-50";

export function usePlatformResource(loader) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await loader());
    } catch (reason) {
      setError(reason.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }, [loader]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, setData, loading, error, setError, reload };
}

export function AdminSection({
  eyebrow,
  title,
  description,
  actions,
  children,
}) {
  const { t } = useLocale();
  return (
    <div className="space-y-5">
      <header className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[.18em] text-[var(--brand-muted)]">
              {eyebrow || t("platformAdministration.title")}
            </p>
            <h2 className="mt-2 text-2xl font-black text-[var(--brand-text)]">
              {title}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-[var(--brand-muted)]">
              {description}
            </p>
          </div>
          {actions ? (
            <div className="flex flex-wrap gap-2">{actions}</div>
          ) : null}
        </div>
      </header>
      {children}
    </div>
  );
}
export function AdminCard({ title, description, children, className = "" }) {
  return (
    <section
      className={`rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm sm:p-6 ${className}`}
    >
      <h3 className="text-lg font-black text-[var(--brand-text)]">{title}</h3>
      {description ? (
        <p className="mt-1 text-sm text-[var(--brand-muted)]">{description}</p>
      ) : null}
      <div className="mt-5">{children}</div>
    </section>
  );
}
export function ResourceState({ loading, error, onRetry }) {
  const { t } = useLocale();
  const localizedError = /network|tarmoq|failed to fetch/i.test(error)
    ? t("errors.network")
    : t("platformAdministration.requestFailed");
  if (loading)
    return (
      <div className="rounded-3xl border bg-[var(--brand-card)] p-8 text-sm text-[var(--brand-muted)]">
        {t("platformAdministration.loadingArea")}
      </div>
    );
  if (error)
    return (
      <div
        role="alert"
        className="rounded-3xl border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-600"
      >
        {localizedError}
        <button type="button" onClick={onRetry} className="ml-3 underline">
          {t("platformAdministration.retry")}
        </button>
      </div>
    );
  return null;
}
export function Notice({ children, tone = "success" }) {
  return (
    <div
      role="status"
      className={`rounded-2xl px-4 py-3 text-sm ${tone === "error" ? "bg-red-500/10 text-red-600" : "bg-emerald-500/10 text-emerald-700"}`}
    >
      {children}
    </div>
  );
}
