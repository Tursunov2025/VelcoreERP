import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import LogisticsSectionNav from "../../components/logistics/LogisticsSectionNav";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage } from "../productionProjects/projectUi";

export default function LogisticsDashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { t } = useLocale();

  useEffect(() => {
    Promise.all([api.finishedTrips(), api.finishedVehicles(true), api.finishedTrackingFleet(), api.finishedLogisticsAlerts(), api.finishedReadyCargo()])
      .then(([trips,vehicles,fleet,alerts,cargo]) => { setStats({trips:trips.trips||[],vehicles:vehicles.vehicles||[],fleet:fleet.items||[],alerts:alerts.alerts||[],cargo}); setError(""); })
      .catch((e) => setError(apiMessage(e,t)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error && !stats) return <div><LogisticsSectionNav/><PageHeader title={t("logisticsCenter.dashboard.title")} subtitle={t("logisticsCenter.dashboard.subtitle")} /><ErrorAlert message={error} onRetry={() => window.location.reload()} /></div>;

  const trips=stats?.trips||[], today=new Date().toDateString();
  const count=(values)=>trips.filter(x=>values.includes(x.status)).length;
  const isToday=(value)=>value && new Date(value).toDateString()===today;
  const todayLoadings=trips.filter(x=>["planned","loading","loaded"].includes(x.status)&&isToday(x.planned_departure_at));
  const activeTrips=trips.filter(x=>["loading","loaded","dispatched","in_transit"].includes(x.status));
  const queue=(status)=>trips.filter(x=>status.includes(x.status));
  const alertTrips=(type)=>new Set((stats?.alerts||[]).filter(x=>x.type===type).map(x=>x.trip_id));
  const onlineGps=(stats?.fleet||[]).filter(x=>x.status==="active").length;
  const cards=[
    ["ready",stats?.cargo?.totals?.package_count||0,"/logistics/shipments"],["loadingToday",todayLoadings.length,"/logistics/loading?view=today"],["loadingNow",count(["loading"]),"/logistics/loading?view=active"],
    ["transit",count(["dispatched","in_transit"])],["delivered",trips.filter(x=>["delivered","accepted"].includes(x.status)&&x.arrived_at&&new Date(x.arrived_at).toDateString()===today).length],
    ["delayed",trips.filter(x=>x.sla_state==="delayed").length],["activeVehicles",(stats?.vehicles||[]).filter(x=>x.is_active).length],["gpsState",`${onlineGps}/${Math.max(0,(stats?.fleet||[]).length-onlineGps)}`],
  ];

  return (
    <div>
      <LogisticsSectionNav/>
      <PageHeader title={t("logisticsCenter.dashboard.title")} subtitle={t("logisticsCenter.dashboard.subtitle")} />
      {error && <ErrorAlert message={error} onRetry={() => window.location.reload()} />}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(([key,value,to])=><StatCard key={key} label={t(`logisticsCenter.metrics.${key}`)} value={value} to={to}/>) }
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <TripList title={t("logisticsCenter.dashboardSections.todayLoadings")} trips={todayLoadings} t={t}/>
        <TripList title={t("logisticsCenter.dashboardSections.activeTrips")} trips={activeTrips} t={t}/>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4"><h2 className="mb-3 font-black">{t("logisticsCenter.readyCargo.title")}</h2>{(stats?.cargo?.projects||[]).slice(0,8).map(x=><Link to={`/logistics/shipments?project_id=${x.project_id}`} className="flex justify-between border-t py-2 text-sm" key={x.project_id}><strong>{x.project_code}</strong><span>{x.package_count} · {x.destination_city}</span></Link>)}{!stats?.cargo?.projects?.length&&<p className="text-[var(--brand-muted)]">{t("logisticsCenter.readyCargo.empty")}</p>}</div>
        <TripList title={t("logisticsCenter.queues.readyDispatch")} trips={queue(["loaded"])} t={t}/>
        <TripList title={t("logisticsCenter.queues.dispatchedNoGps")} trips={trips.filter(x=>alertTrips("DISPATCHED_NO_GPS").has(x.id))} t={t}/>
        <TripList title={t("logisticsCenter.queues.arrivalPending")} trips={queue(["in_transit"])} t={t}/>
        <TripList title={t("logisticsCenter.queues.deliveryPending")} trips={queue(["arrived"])} t={t}/>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4"><h2 className="mb-3 font-black">{t("logisticsCenter.dashboardSections.problems")}</h2>{(stats?.alerts||[]).map((x,i)=><p className="border-t py-2 text-sm" key={`${x.trip_id}-${x.type}-${i}`}>{t(`logisticsCenter.alerts.${x.type}`)} · #{x.trip_id}</p>)}{!stats?.alerts?.length&&<p className="text-sm text-[var(--brand-muted)]">{t("logisticsCenter.empty")}</p>}</div>
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4"><h2 className="mb-3 font-black">{t("logisticsCenter.dashboardSections.gps")}</h2>{(stats?.fleet||[]).slice(0,8).map(x=><div className="flex justify-between border-t py-2 text-sm" key={x.vehicle_id}><strong>{x.registration_number}</strong><span>{t(`checkpointD.tracking.health.${x.status||"offline"}`)}</span></div>)}{!stats?.fleet?.length&&<p className="text-[var(--brand-muted)]">{t("logisticsCenter.empty")}</p>}</div>
      </div>
    </div>
  );
}

function TripList({title,trips,t}) { return <div className="rounded-2xl border bg-[var(--brand-card)] p-4"><h2 className="mb-3 font-black">{title}</h2>{trips.slice(0,8).map(x=><div className="flex justify-between gap-3 border-t py-2 text-sm" key={x.id}><strong>{x.trip_number}</strong><span className="text-right">{x.destination_city} · {t(`checkpointD.status.${x.status}`)}</span></div>)}{!trips.length&&<p className="text-[var(--brand-muted)]">{t("logisticsCenter.empty")}</p>}</div> }

function StatCard({ label, value, to }) {
  return (
    <Link to={to || "/logistics/shipments"} className="rounded-2xl border bg-[var(--brand-card)] p-4 hover:shadow-sm">
      <p className="text-xs uppercase text-[var(--brand-muted)]">{label}</p>
      <p className="text-2xl font-black">{value}</p>
    </Link>
  );
}
