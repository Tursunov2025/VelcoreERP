import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function LogoutButton({ className = "", compact = false }) {
  const { logout } = useAuth();
  const { t } = useLocale();
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        className={className}
        style={className ? undefined : { backgroundColor: "var(--brand-danger)" }}
      >
        {compact ? t("common.logout") : `⎋ ${t("common.logout")}`}
      </button>

      {confirmOpen ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-3xl bg-white p-6 text-[var(--brand-text)] shadow-2xl">
            <h2 className="text-xl font-black">{t("common.logoutConfirmTitle")}</h2>
            <p className="mt-2 text-sm text-gray-600">{t("common.logoutConfirmText")}</p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="rounded-xl border px-4 py-2 text-sm font-semibold"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={logout}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white"
              >
                {t("common.logout")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

