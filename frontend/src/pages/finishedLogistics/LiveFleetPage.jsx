import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage, date, panel } from "../productionProjects/projectUi";

export default function LiveFleetPage() {
  const { t, locale } = useLocale();
  const [data, setData] = useState({ items: [] });
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [filters, setFilters] = useState({ driver_user_id: "", vehicle_id: "" });
  const [mode, setMode] = useState("all");
  const [error, setError] = useState("");
  const [alerts, setAlerts] = useState([]);
  const yandexKey = import.meta.env.VITE_YANDEX_MAPS_API_KEY || "";
  const load = useCallback(async () => {
    try { const [fleet, alertData] = await Promise.all([api.finishedTrackingFleet(filters), api.finishedLogisticsAlerts()]); setData(fleet); setAlerts(alertData.alerts || []); setError(""); }
    catch (e) { setError(apiMessage(e, t)); }
  }, [filters, t]);
  useEffect(() => { load(); const timer=setInterval(load, 30000); return () => clearInterval(timer); }, [load]);
  useEffect(() => { const tripId=typeof selected==="number"?selected:null;if (!tripId) { setHistory([]); return; } api.finishedTripTracking(tripId, 500).then((r) => setHistory(r.history || [])).catch((e) => setError(apiMessage(e,t))); }, [selected,t]);
  const drivers=useMemo(()=>[...new Set(data.items.map(x=>x.driver_user_id).filter(Boolean))],[data]);
  const vehicles=useMemo(()=>[...new Map(data.items.map(x=>[x.vehicle_id,x.registration_number])).entries()],[data]);
  const visible=useMemo(()=>data.items.filter(x=>mode==="all"||(mode==="online"&&x.status==="active")||(mode==="offline"&&x.status!=="active")||(mode==="activeTrip"&&x.trip_id)||(mode==="noTrip"&&!x.trip_id)),[data,mode]);
  const itemKey=x=>x.trip_id||`vehicle-${x.vehicle_id}`;
  const selectedItem=data.items.find(x=>itemKey(x)===selected);
  const points=history.map(x=>[x.longitude,x.latitude]);
  const bounds=points.length ? { minX:Math.min(...points.map(p=>p[0])),maxX:Math.max(...points.map(p=>p[0])),minY:Math.min(...points.map(p=>p[1])),maxY:Math.max(...points.map(p=>p[1])) } : null;
  const polyline=bounds ? points.map(([x,y])=>`${10+380*(x-bounds.minX)/(bounds.maxX-bounds.minX||1)},${190-180*(y-bounds.minY)/(bounds.maxY-bounds.minY||1)}`).join(" ") : "";
  return <section className="space-y-4">
    <header><h1 className="text-2xl font-black">{t("checkpointD.tracking.fleetTitle")}</h1><p className="text-sm text-[var(--brand-muted)]">{t("checkpointD.tracking.fleetNotice")}</p></header>
    {error && <ErrorAlert message={error} onRetry={load}/>} 
    {alerts.length>0&&<div className="grid gap-2">{alerts.map((alert,i)=><p className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" key={`${alert.trip_id}-${alert.type}-${i}`}>{t(`logisticsCenter.alerts.${alert.type}`)} · #{alert.trip_id}</p>)}</div>}
    <div className="flex flex-wrap gap-2">{["all","online","offline","activeTrip","noTrip"].map(x=><button key={x} onClick={()=>setMode(x)} className={`rounded-full border px-3 py-1.5 text-sm ${mode===x?"font-black text-white":""}`} style={mode===x?{backgroundColor:"var(--brand-button)"}:undefined}>{t(`logisticsCenter.gps.filters.${x}`)}</button>)}</div>
    <div className={`${panel} grid gap-3 sm:grid-cols-2`}>
      <select className="rounded-xl border p-2" value={filters.driver_user_id} onChange={e=>setFilters({...filters,driver_user_id:e.target.value})}><option value="">{t("checkpointD.tracking.allDrivers")}</option>{drivers.map(id=><option key={id} value={id}>#{id}</option>)}</select>
      <select className="rounded-xl border p-2" value={filters.vehicle_id} onChange={e=>setFilters({...filters,vehicle_id:e.target.value})}><option value="">{t("checkpointD.tracking.allVehicles")}</option>{vehicles.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select>
    </div>
    <div className="grid min-w-0 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]"><div className={`${panel} max-h-[620px] space-y-2 overflow-y-auto`}>{visible.map(x=><button type="button" key={itemKey(x)} onClick={()=>setSelected(itemKey(x))} className={`w-full rounded-xl border p-3 text-left ${selected===itemKey(x)?"ring-2 ring-[var(--brand-primary)]":""}`}><strong>{x.registration_number}</strong><span className="float-right text-xs">{t(`checkpointD.tracking.health.${x.status}`)}</span><p className="text-sm">{x.trip_number||t("logisticsCenter.gps.noTrip")} · {x.driver_name||t("checkpointD.values.missing")}</p><p className="text-xs text-[var(--brand-muted)]">{x.destination_city||t("checkpointD.values.missing")} · {date(x.last_contact_at,locale)}</p></button>)}</div><div className={panel}><h2 className="font-black">{selectedItem?.registration_number||t("checkpointD.tracking.selectTrip")}</h2>{selectedItem&&<div className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><p>{t("checkpointD.tracking.trip")}: {selectedItem.trip_id?<Link className="font-bold" to={`/logistics/shipments/${selectedItem.trip_id}`}>{selectedItem.trip_number}</Link>:t("logisticsCenter.gps.noTrip")}</p><p>{t("checkpointD.fields.driver_name")}: {selectedItem.driver_name||t("checkpointD.values.missing")}</p><p>{t("checkpointD.fields.destination")}: {selectedItem.destination_city?`${selectedItem.destination_city} · ${selectedItem.destination_site}`:t("checkpointD.values.missing")}</p><p>{t("checkpointD.tracking.status")}: {t(`checkpointD.tracking.health.${selectedItem.status}`)}</p><p>{t("logisticsCenter.gps.session")}: {selectedItem.session_id?`#${selectedItem.session_id}`:"—"}</p><p>{t("logisticsCenter.gps.started")}: {date(selectedItem.session_started_at,locale)}</p><p>{t("checkpointD.tracking.last")}: {date(selectedItem.last_contact_at,locale)}</p><p>{t("checkpointD.tracking.speed")}: {selectedItem.latest?.speed_kmh??"—"}</p><p className="sm:col-span-2">{t("checkpointD.tracking.latest")}: {selectedItem.latest?`${Number(selectedItem.latest.latitude).toFixed(5)}, ${Number(selectedItem.latest.longitude).toFixed(5)}`:"—"}</p></div>}<h3 className="mt-5 font-black">{t("checkpointD.tracking.travelled")}</h3>{!selectedItem?.trip_id?<p>{t("checkpointD.tracking.selectTrip")}</p>:points.length<2?<p>{t("checkpointD.tracking.noRoute")}</p>:<svg viewBox="0 0 400 200" className="mt-3 w-full rounded-xl border"><polyline points={polyline} fill="none" stroke="var(--brand-primary)" strokeWidth="4"/></svg>}{!yandexKey&&<p className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-900">{t("checkpointD.tracking.yandexMissing")}</p>}</div></div>
  </section>;
}
