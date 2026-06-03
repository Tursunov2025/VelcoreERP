import { useLocale } from "../../context/LocaleContext";

export default function MobileUpdateModal({
  open,
  forceUpdate,
  latest,
  downloading,
  error,
  onUpdate,
  onLater,
}) {
  const { t } = useLocale();
  if (!open || !latest) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-xl font-black text-gray-900">{t("mobileUpdate.title")}</h2>
        <p className="mt-1 text-sm text-gray-600">
          {latest.latest_version} (build {latest.version_code})
        </p>
        {latest.release_notes ? (
          <div className="mt-4 rounded-xl border bg-gray-50 p-3 text-sm text-gray-800 whitespace-pre-wrap">
            {latest.release_notes}
          </div>
        ) : null}
        {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
        {forceUpdate ? (
          <p className="mt-3 text-sm font-semibold text-amber-700">{t("mobileUpdate.forceHint")}</p>
        ) : null}
        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            disabled={downloading}
            onClick={onUpdate}
            className="brand-btn flex-1 rounded-xl py-3 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {downloading ? t("mobileUpdate.downloading") : t("mobileUpdate.updateNow")}
          </button>
          {!forceUpdate ? (
            <button
              type="button"
              disabled={downloading}
              onClick={onLater}
              className="flex-1 rounded-xl border py-3 font-bold text-gray-700"
            >
              {t("mobileUpdate.later")}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
