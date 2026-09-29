import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage, date, number, panel } from "./projectUi";
export default function ProductionProjectDetailPage() {
  const { id } = useParams();
  const { t, locale } = useLocale();
  const [s, setS] = useState({
    loading: true,
    error: "",
    project: null,
    progress: null,
    forecast: null,
    trips: [],
  });
  const load = useCallback(async () => {
    try {
      const [project, progress, trips] = await Promise.all([
        api.productionProject(id),
        api.productionProjectProgress(id),
        api.finishedTrips({ project_id: id }).catch(() => ({ trips: [] })),
      ]);
      const forecast = await api
        .productionProjectForecast(id)
        .catch(() => null);
      setS({
        loading: false,
        error: "",
        project,
        progress,
        forecast,
        trips: trips.trips || [],
      });
    } catch (e) {
      setS((x) => ({ ...x, loading: false, error: apiMessage(e, t) }));
    }
  }, [id, t]);
  useEffect(() => {
    load();
  }, [load]);
  if (s.loading)
    return <div className={panel}>{t("checkpointD.actions.loading")}</div>;
  if (s.error) return <ErrorAlert message={s.error} onRetry={load} />;
  const p = s.project,
    pr = s.progress || {},
    latest = s.trips[0];
  const total = (p.lines || []).reduce((a, x) => a + Number(x.quantity), 0);
  const facts = [
    "produced_quantity",
    "quality_approved_quantity",
    "packaged_quantity",
    "shipped_quantity",
    "delivered_quantity",
    "accepted_quantity",
    "damaged_quantity",
    "missing_quantity",
  ].map((k) => [k, (p.lines || []).reduce((a, x) => a + Number(x[k] || 0), 0)]);
  return (
    <section className="space-y-4">
      <header className="flex flex-wrap justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">
            {p.project_code} · {p.project_name}
          </h1>
          <p>
            {p.destination_city} — {number(pr.overall_progress_percent, locale)}
            % {t("checkpointD.detail.ready")}
          </p>
          <p className="text-sm text-[var(--brand-muted)]">
            {p.customer_name_snapshot} · {p.site_name} · {p.full_address}
          </p>
        </div>
        {["draft", "planned"].includes(p.status) && (
          <Link
            className="rounded-xl border px-4 py-2"
            to={`/production-projects/${p.id}/edit`}
          >
            {t("checkpointD.actions.edit")}
          </Link>
        )}
      </header>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className={panel}>
          <small>{t("checkpointD.fields.total")}</small>
          <strong className="block text-2xl">{number(total, locale)}</strong>
        </div>
        <div className={panel}>
          <small>{t("checkpointD.fields.production")}</small>
          <strong className="block">
            {t(`checkpointD.status.${p.status}`)}
          </strong>
        </div>
        <div className={panel}>
          <small>{t("checkpointD.fields.logistics")}</small>
          <strong className="block">
            {latest ? t(`checkpointD.status.${latest.status}`) : "—"}
          </strong>
        </div>
        <div className={panel}>
          <small>{t("checkpointD.detail.forecast")}</small>
          <strong className="block">
            {s.forecast?.forecast_at
              ? date(s.forecast.forecast_at, locale)
              : "—"}
          </strong>
        </div>
      </div>
      <div className={`${panel} grid gap-3 sm:grid-cols-3 lg:grid-cols-4`}>
        {facts.map(([k, v]) => (
          <div key={k}>
            <span className="text-sm text-[var(--brand-muted)]">
              {t(`checkpointD.metrics.${k}`)}
            </span>
            <strong className="block text-xl">{number(v, locale)}</strong>
          </div>
        ))}
      </div>
      <div className={panel}>
        <h2 className="mb-3 text-lg font-black">
          {t("checkpointD.detail.products")}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr>
                {[
                  "product",
                  "ordered",
                  "produced",
                  "qc",
                  "packaged",
                  "warehouse",
                  "loaded",
                  "delivered",
                  "accepted",
                ].map((x) => (
                  <th className="p-2 text-left" key={x}>
                    {t(`checkpointD.fields.${x}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(p.lines || []).map((x) => (
                <tr className="border-t" key={x.id}>
                  <td className="p-2">
                    <strong>{x.product_code}</strong>
                    <br />
                    {x.product_name}
                  </td>
                  {[
                    x.quantity,
                    x.produced_quantity,
                    x.quality_approved_quantity,
                    x.packaged_quantity,
                    x.packaged_quantity,
                    x.shipped_quantity,
                    x.delivered_quantity,
                    x.accepted_quantity,
                  ].map((v, i) => (
                    <td className="p-2" key={i}>
                      {number(v, locale)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className={panel}>
        <h2 className="text-lg font-black">
          {t("checkpointD.detail.timeline")}
        </h2>
        {s.trips.length === 0 ? (
          <p className="mt-2 text-[var(--brand-muted)]">
            {t("checkpointD.detail.noOperations")}
          </p>
        ) : (
          <ol className="mt-3 border-l pl-5">
            {s.trips.map((x) => (
              <li className="mb-4" key={x.id}>
                <Link
                  to={`/mes/finished-logistics/trips/${x.id}`}
                  className="font-bold text-[var(--brand-primary)]"
                >
                  {x.trip_number}
                </Link>
                <p>
                  {t(`checkpointD.status.${x.status}`)} ·{" "}
                  {date(x.updated_at, locale)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
