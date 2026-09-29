export const projectStatuses = ["draft", "planned", "released", "in_production", "partially_ready", "ready_to_ship", "shipped", "partially_delivered", "delivered", "completed", "cancelled"];
export const tripStatuses = ["draft", "planned", "loading", "loaded", "dispatched", "in_transit", "delivered", "accepted", "cancelled"];

export function number(value, locale = "uz") {
  return new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "uz-UZ", { maximumFractionDigits: 2 }).format(Number(value || 0));
}

export function date(value, locale = "uz") {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "uz-UZ", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function apiMessage(error, t) {
  if (error?.code === "request_cancelled") return "";
  if (error?.code === "network_error") return t("errors.network");
  if (error?.status === 403 || error?.message?.includes("403")) return t("checkpointD.errors.permission");
  const code = error?.data?.detail?.code || error?.code;
  if (code) {
    const key = `checkpointD.errors.${code}`;
    const translated = t(key);
    return translated && translated !== key ? translated : t("checkpointD.errors.generic");
  }
  return error?.message || t("checkpointD.errors.generic");
}

export function idempotency(scope) {
  return `${scope}-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`}`;
}

export const panel = "rounded-2xl border border-[var(--brand-border,#d1d5db)] bg-[var(--brand-card)] p-4 shadow-sm";
export const field = "w-full rounded-xl border border-[var(--brand-border,#d1d5db)] bg-[var(--brand-card)] px-3 py-2 text-[var(--brand-text)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)]";
export const button = "rounded-xl px-4 py-2 font-semibold focus:outline-none focus:ring-2 focus:ring-[var(--brand-focus)] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
