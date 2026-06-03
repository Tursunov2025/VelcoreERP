import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function MesQcRejectionReasonsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("mes_edit");

  const [reasons, setReasons] = useState([]);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canEdit) return;
    setError("");
    try {
      const data = await api.mesQcAdminRejectionReasons(true);
      setReasons(data.reasons || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => {
    load();
  }, [load]);

  const addReason = async () => {
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    setToast("");
    try {
      await api.mesQcAdminCreateRejectionReason({ name, sort_order: reasons.length });
      setNewName("");
      await load();
      setToast(t("mes.qcReasonSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (reason) => {
    setBusy(true);
    setToast("");
    try {
      await api.mesQcAdminUpdateRejectionReason(reason.id, { is_active: !reason.is_active });
      await load();
      setToast(t("mes.qcReasonSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!canEdit) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link
        to="/mes/terminal/qc"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.qcTerminal")}
      </Link>

      <PageHeader title={t("mes.qcRejectionReasons")} subtitle={t("mes.qcRejectionReasonsDesc")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-4 flex gap-2">
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder={t("mes.qcReasonNamePlaceholder")}
          className="min-h-[48px] flex-1 rounded-xl border px-3"
          disabled={busy}
        />
        <button
          type="button"
          disabled={busy || !newName.trim()}
          onClick={addReason}
          className="min-h-[48px] rounded-xl px-5 font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("common.add")}
        </button>
      </div>

      <div className="space-y-2">
        {reasons.map((reason) => (
          <div
            key={reason.id}
            className={`flex items-center justify-between rounded-xl border p-4 ${
              reason.is_active ? "bg-[var(--brand-card)]" : "opacity-60"
            }`}
          >
            <span className="font-semibold">{reason.name}</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => toggleActive(reason)}
              className="min-h-[44px] rounded-xl border px-4 text-sm font-bold"
            >
              {reason.is_active ? t("mes.qcReasonDeactivate") : t("mes.qcReasonActivate")}
            </button>
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
