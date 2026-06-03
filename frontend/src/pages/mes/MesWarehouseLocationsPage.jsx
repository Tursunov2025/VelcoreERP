import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function MesWarehouseLocationsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("mes_edit");

  const [locations, setLocations] = useState([]);
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canEdit) return;
    setError("");
    try {
      const data = await api.mesWarehouseAdminLocations(true);
      setLocations(data.locations || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => {
    load();
  }, [load]);

  const addLocation = async () => {
    const trimmed = code.trim();
    if (!trimmed) return;
    setBusy(true);
    setToast("");
    try {
      await api.mesWarehouseAdminCreateLocation({ code: trimmed, description: description.trim() });
      setCode("");
      setDescription("");
      await load();
      setToast(t("mes.warehouseLocationSaved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (loc) => {
    setBusy(true);
    setToast("");
    try {
      await api.mesWarehouseAdminUpdateLocation(loc.id, { is_active: !loc.is_active });
      await load();
      setToast(t("mes.warehouseLocationSaved"));
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
        to="/mes/terminal/warehouse"
        className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]"
      >
        ← {t("mes.warehouseTerminal")}
      </Link>

      <PageHeader title={t("mes.warehouseLocations")} subtitle={t("mes.warehouseLocationsDesc")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="A-01-01"
          className="min-h-[48px] rounded-xl border px-3 font-mono font-bold"
          disabled={busy}
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("mes.locationDescription")}
          className="min-h-[48px] rounded-xl border px-3 sm:col-span-1"
          disabled={busy}
        />
        <button
          type="button"
          disabled={busy || !code.trim()}
          onClick={addLocation}
          className="min-h-[48px] rounded-xl font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("common.add")}
        </button>
      </div>

      <div className="space-y-2">
        {locations.map((loc) => (
          <div
            key={loc.id}
            className={`flex items-center justify-between rounded-xl border p-4 ${
              loc.is_active ? "bg-[var(--brand-card)]" : "opacity-60"
            }`}
          >
            <div>
              <p className="font-mono font-bold">{loc.code}</p>
              {loc.description ? (
                <p className="text-sm text-[var(--brand-muted)]">{loc.description}</p>
              ) : null}
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => toggleActive(loc)}
              className="min-h-[44px] rounded-xl border px-4 text-sm font-bold"
            >
              {loc.is_active ? t("mes.warehouseLocationDeactivate") : t("mes.warehouseLocationActivate")}
            </button>
          </div>
        ))}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
