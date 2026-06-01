import { useEffect, useState } from "react";
import { useLocale } from "../../context/LocaleContext";

const LOCALE_MAP = {
  uz_latn: "uz-UZ",
  uz_cyrl: "uz-UZ",
  ru: "ru-RU",
  en: "en-GB",
  kz: "kk-KZ",
  ky: "ky-KG",
  tr: "tr-TR",
};

export default function DashboardClock() {
  const { clockFormat, clockTimezone, language, t } = useLocale();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const locale = LOCALE_MAP[language] || "uz-UZ";
  const hour12 = clockFormat === "12h";

  const time = new Intl.DateTimeFormat(locale, {
    timeZone: clockTimezone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12,
  }).format(now);

  const date = new Intl.DateTimeFormat(locale, {
    timeZone: clockTimezone,
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(now);

  return (
    <div
      className="brand-surface rounded-[var(--brand-radius)] p-6 text-white shadow-[var(--brand-shadow)]"
      style={{ backgroundColor: "var(--brand-sidebar)" }}
    >
      <p className="text-sm opacity-80">{t("dashboard.currentTime")}</p>
      <h2 className="mt-2 font-mono text-3xl font-black tracking-wide md:text-4xl">
        {time}
      </h2>
      <p className="mt-3 text-sm opacity-90">
        {t("dashboard.currentDate")}: {date}
      </p>
    </div>
  );
}
