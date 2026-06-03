import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { PRODUCTION_STAGES } from "../../constants/workflow";
import { useLocale } from "../../context/LocaleContext";
import Toast from "../ui/Toast";

function parseJsonArray(raw, fallback) {
  try {
    const v = JSON.parse(raw || "[]");
    return Array.isArray(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

export default function ProductionStagesManagerTab() {
  const { t } = useLocale();
  const [legacyStages, setLegacyStages] = useState([...PRODUCTION_STAGES]);
  const [mesStages, setMesStages] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    api
      .adminGetProductionSettings()
      .then((data) => {
        setLegacyStages(parseJsonArray(data.production_stages_json, PRODUCTION_STAGES));
        setDepartments(parseJsonArray(data.departments_json, []));
        setMesStages(parseJsonArray(data.mes_default_stages_json, []));
      })
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.adminUpdateProductionSettings({
        production_stages_json: JSON.stringify(legacyStages.filter(Boolean)),
        departments_json: JSON.stringify(departments.filter(Boolean)),
        mes_default_stages_json: JSON.stringify(
          mesStages.filter((row) => row[0] && row[1])
        ),
      });
      setToast(t("controlCenter.saved"));
    } catch (e) {
      setToast(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>{t("common.loading")}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-2 text-xl font-black">{t("controlCenter.stagesTitle")}</h2>
        <p className="text-sm text-[var(--brand-muted)]">{t("controlCenter.stagesSubtitle")}</p>
      </div>

      <section className="rounded-2xl border bg-white p-4">
        <h3 className="mb-3 font-bold">{t("controlCenter.legacyStages")}</h3>
        <div className="space-y-2">
          {legacyStages.map((stage, i) => (
            <div key={i} className="flex gap-2">
              <input
                value={stage}
                onChange={(e) => {
                  const next = [...legacyStages];
                  next[i] = e.target.value;
                  setLegacyStages(next);
                }}
                className="min-h-[44px] flex-1 rounded-xl border px-3"
              />
              <button
                type="button"
                className="rounded-xl border px-3 text-red-600"
                onClick={() => setLegacyStages(legacyStages.filter((_, j) => j !== i))}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="mt-2 text-sm font-semibold text-[var(--brand-primary)]"
          onClick={() => setLegacyStages([...legacyStages, ""])}
        >
          + {t("common.add")}
        </button>
      </section>

      <section className="rounded-2xl border bg-white p-4">
        <h3 className="mb-3 font-bold">{t("controlCenter.mesRouteStages")}</h3>
        <p className="mb-2 text-xs text-gray-500">[Bosqich nomi, Bo&apos;lim]</p>
        <div className="space-y-2">
          {mesStages.map((row, i) => (
            <div key={i} className="grid grid-cols-2 gap-2">
              <input
                value={row[0] || ""}
                placeholder="Lazer"
                onChange={(e) => {
                  const next = [...mesStages];
                  next[i] = [e.target.value, next[i]?.[1] || ""];
                  setMesStages(next);
                }}
                className="min-h-[44px] rounded-xl border px-3"
              />
              <input
                value={row[1] || ""}
                placeholder="Kesish"
                onChange={(e) => {
                  const next = [...mesStages];
                  next[i] = [next[i]?.[0] || "", e.target.value];
                  setMesStages(next);
                }}
                className="min-h-[44px] rounded-xl border px-3"
              />
            </div>
          ))}
        </div>
        <button
          type="button"
          className="mt-2 text-sm font-semibold text-[var(--brand-primary)]"
          onClick={() => setMesStages([...mesStages, ["", ""]])}
        >
          + {t("common.add")}
        </button>
      </section>

      <button
        type="button"
        disabled={saving}
        onClick={save}
        className="brand-btn rounded-xl px-6 py-3 font-bold text-white"
        style={{ backgroundColor: "var(--brand-button)" }}
      >
        {saving ? t("common.saving") : t("common.save")}
      </button>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
