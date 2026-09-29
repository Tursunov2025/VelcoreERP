import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Card from "../../components/ui/Card";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

const statusLabel = (t, value) => {
  const key = { created: "statusCreated", packed: "statusPacked", received: "statusReceived", in_warehouse: "statusReceived", placed: "statusPlaced", loaded: "statusLoaded", shipped: "statusShipped", dispatched: "statusShipped", in_transit: "statusTransit", arrived: "statusArrived", delivered: "statusDelivered", accepted: "statusAccepted", finished: "statusFinished" }[String(value || "").toLowerCase()];
  return key ? t(`traceability.${key}`) : (value || "—");
};
const stageLabel = (t, row) => {
  const key = String(row?.stage_key || row?.stage_name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const known = { project: "stageProject", mes_release: "stageRelease", lazer: "stageLazer", laser: "stageLazer", svarka: "stageSvarka", svarshik: "stageSvarka", kraska: "stageKraska", painting: "stageKraska", qc: "stageQc", inspection: "stageQc", packaging: "stagePackaging", upakovka: "stagePackaging", warehouse: "stageWarehouse", sklad: "stageWarehouse", loading: "stageLoading", yuklash: "stageLoading", dispatch: "stageDispatch", gps_in_transit: "stageGps", arrival: "stageArrival", delivery: "stageDelivery", acceptance: "stageAcceptance" }[key] || (key.startsWith("rework_") ? "rework" : null);
  return known ? t(`traceability.${known}`) : (row?.stage_name || "—");
};
const localizedError = (t, error) => error?.code === "passport_not_found" ? t("traceability.notFound") : (error?.code === "network_error" ? t("traceability.errorNetwork") : (error?.message || t("traceability.error")));

export default function PublicProductPassportPage() {
  const { token } = useParams(); const { t } = useLocale(); const [data, setData] = useState(null); const [error, setError] = useState("");
  useEffect(() => { api.publicProductPassport(token).then(setData).catch((e) => setError(localizedError(t, e))); }, [token]);
  if (error) return <ErrorAlert message={error} />;
  if (!data) return <div className="flex min-h-[35vh] items-center justify-center"><LoadingSpinner label={t("traceability.loading")} /></div>;
  return <div className="mx-auto max-w-3xl space-y-4"><Card><p className="text-xs uppercase tracking-wide text-[var(--brand-muted)]">{t("traceability.publicView")}</p><h1 className="mt-1 text-2xl font-bold">{data.serial_number}</h1><p className="mt-2 text-lg">{data.product_code} — {data.product_name}</p><p className="mt-2 text-sm">{t("traceability.project")}: {[data.project?.code, data.project?.name].filter(Boolean).join(" — ") || "—"}</p><p className="text-sm">{t("traceability.status")}: {statusLabel(t, data.status)}</p></Card><Card><h2 className="mb-3 text-lg font-bold">{t("traceability.timeline")}</h2><ul className="space-y-2">{(data.timeline || []).map((row) => <li key={row.stage_key} className="flex flex-wrap justify-between gap-2 rounded-xl border p-3 text-sm"><span className="font-semibold">{stageLabel(t, row)}</span><span>{row.completed_at || row.started_at || "—"}</span></li>)}</ul></Card></div>;
}
