import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import FleetMap from "../../components/gps/FleetMap";
import LogisticsSectionNav from "../../components/logistics/LogisticsSectionNav";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage, panel } from "../productionProjects/projectUi";

const inputClass = "w-full rounded-xl border border-[var(--brand-border)] bg-[var(--brand-surface)] px-3 py-2 text-sm";
const emptyForm = { device_identifier: "", vehicle_id: "", driver_user_id: "", protocol: "sinotrack_h02", notes: "", status: "active" };
const FILTERS = ["all", "moving", "stopped", "trip", "offline", "unbound"];
const STATUS_DOT = { moving: "bg-green-600", stopped: "bg-yellow-500", waiting: "bg-blue-600", stale: "bg-red-600", offline: "bg-red-600", no_signal: "bg-slate-500", unbound: "bg-slate-500" };

function fmtDate(value, locale) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "uz-UZ", { dateStyle: "short", timeStyle: "medium" }).format(parsed);
}

function relativeAge(seconds, locale, t) {
  if (seconds == null) return "—";
  if (seconds < 60) return t("gpsMonitor.ageSeconds", { count: Math.max(0, Math.floor(seconds)) });
  if (seconds < 3600) return t("gpsMonitor.ageMinutes", { count: Math.floor(seconds / 60) });
  return t("gpsMonitor.ageHours", { count: Math.floor(seconds / 3600) });
}

export default function CanonicalGpsPage() {
  const { t, locale } = useLocale();
  const [fleet, setFleet] = useState({ items: [], generated_at: null }), [vehicles, setVehicles] = useState([]), [drivers, setDrivers] = useState([]), [devices, setDevices] = useState([]);
  const [selectedId, setSelectedId] = useState(null), [history, setHistory] = useState([]), [query, setQuery] = useState(""), [filter, setFilter] = useState("all");
  const [form, setForm] = useState(emptyForm), [showForm, setShowForm] = useState(false), [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const loadingRef = useRef(false), selectedRef = useRef(null);
  useEffect(() => { selectedRef.current = selectedId; }, [selectedId]);

  const load = useCallback(async () => {
    if (loadingRef.current || document.visibilityState === "hidden") return;
    loadingRef.current = true;
    try {
      const [fleetData, vehicleData, driverData, deviceData] = await Promise.all([api.finishedTrackingFleet(), api.finishedVehicles(true), api.finishedDrivers(true), api.finishedGpsDevices(true)]);
      setFleet(fleetData); setVehicles(vehicleData.vehicles || []); setDrivers(driverData.drivers || []); setDevices(deviceData.devices || []); setError("");
      const current = selectedRef.current;
      const items = fleetData.items || [];
      if (!current && items.length) setSelectedId((items.find((item) => item.latest)?.vehicle_id) || items[0].vehicle_id);
      else if (current && !items.some((item) => item.vehicle_id === current)) setSelectedId(items[0]?.vehicle_id || null);
    } catch (e) { setError(apiMessage(e, t)); }
    finally { loadingRef.current = false; setLoading(false); }
  }, [t]);

  useEffect(() => { load(); const timer = window.setInterval(load, 10000); return () => window.clearInterval(timer); }, [load]);
  const rawSelected = fleet.items.find((item) => item.vehicle_id === selectedId) || null;
  useEffect(() => {
    let cancelled = false;
    if (!rawSelected?.trip_id) { setHistory([]); return undefined; }
    api.finishedTripTracking(rawSelected.trip_id, 100).then((result) => { if (!cancelled) setHistory(result.history || []); }).catch((e) => { if (!cancelled) setError(apiMessage(e, t)); });
    return () => { cancelled = true; };
  }, [rawSelected?.trip_id, fleet.generated_at, t]);

  const decorated = useMemo(() => fleet.items.map((item) => ({ ...item, status_label: t(`gpsMonitor.status.${item.status}`), last_signal_label: relativeAge(item.seconds_since_signal, locale, t) })), [fleet.items, locale, t]);
  const selected = decorated.find((item) => item.vehicle_id === selectedId) || null;
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return decorated.filter((item) => {
      const filterMatch = filter === "all" || (filter === "trip" ? Boolean(item.trip_id) : filter === "offline" ? ["stale", "offline"].includes(item.status) : filter === "unbound" ? ["unbound", "no_signal"].includes(item.status) : item.status === filter);
      const searchMatch = !needle || [item.registration_number, item.vehicle_model, item.vehicle_type, item.driver_name, item.trip_number].some((value) => String(value || "").toLocaleLowerCase().includes(needle));
      return filterMatch && searchMatch;
    });
  }, [decorated, filter, query]);
  const counts = useMemo(() => ({ total: decorated.length, moving: decorated.filter((x) => x.status === "moving").length, stopped: decorated.filter((x) => x.status === "stopped").length, trip: decorated.filter((x) => x.trip_id).length, offline: decorated.filter((x) => ["stale", "offline"].includes(x.status)).length }), [decorated]);

  const openCreate = (vehicleId = "") => { setEditing(null); setForm({ ...emptyForm, vehicle_id: vehicleId ? String(vehicleId) : "" }); setShowForm(true); setError(""); };
  const openEdit = (device) => { setEditing(device); setForm({ device_identifier: device.device_identifier, vehicle_id: String(device.vehicle_id), driver_user_id: device.driver_user_id ? String(device.driver_user_id) : "", protocol: device.protocol || "custom_http", notes: device.notes || "", status: device.status }); setShowForm(true); setError(""); };
  const saveDevice = async (event) => { event.preventDefault(); setBusy(true); setError(""); try { const body = { ...form, vehicle_id: Number(form.vehicle_id), driver_user_id: form.driver_user_id ? Number(form.driver_user_id) : null }; if (editing) await api.finishedGpsDeviceUpdate(editing.id, { ...body, expected_version: editing.version }); else await api.finishedGpsDeviceCreate(body); setShowForm(false); setEditing(null); setForm(emptyForm); await load(); } catch (e) { setError(apiMessage(e, t)); } finally { setBusy(false); } };
  const unbind = async (device) => { setBusy(true); try { await api.finishedGpsDeviceUnbind(device.id, { expected_version: device.version }); await load(); } catch (e) { setError(apiMessage(e, t)); } finally { setBusy(false); } };
  const labels = useMemo(() => ({ driver: t("gpsMonitor.driver"), speed: t("gpsMonitor.speed"), trip: t("gpsMonitor.trip"), lastSignal: t("gpsMonitor.lastSignal"), status: t("gpsMonitor.state") }), [t]);

  return <section className="min-w-0 space-y-4">
    <LogisticsSectionNav />
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-black">{t("gpsMonitor.title")}</h1><p className="text-sm text-[var(--brand-muted)]">{t("gpsMonitor.subtitle")}</p></div><div className="flex gap-2"><button type="button" onClick={load} disabled={loadingRef.current} className="rounded-xl border px-4 py-2 text-sm font-bold">{t("gpsMonitor.refresh")}</button><button type="button" onClick={() => openCreate()} className="rounded-xl px-4 py-2 text-sm font-bold text-white" style={{ backgroundColor: "var(--brand-button)" }}>{t("gpsMonitor.addDevice")}</button></div></header>
    {error && <ErrorAlert message={error} onRetry={load} />}
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">{[["total", counts.total], ["moving", counts.moving], ["stopped", counts.stopped], ["trip", counts.trip], ["offline", counts.offline]].map(([key, value]) => <article className={`${panel} p-4`} key={key}><p className="text-xs font-bold uppercase text-[var(--brand-muted)]">{t(`gpsMonitor.summary.${key}`)}</p><strong className="mt-1 block text-2xl">{value}</strong></article>)}<article className={`${panel} col-span-2 p-4 lg:col-span-1`}><p className="text-xs font-bold uppercase text-[var(--brand-muted)]">{t("gpsMonitor.summary.updated")}</p><strong className="mt-1 block text-sm">{fmtDate(fleet.generated_at, locale)}</strong></article></div>

    {showForm && <form onSubmit={saveDevice} className={`${panel} grid gap-3 md:grid-cols-2`}><h2 className="text-lg font-black md:col-span-2">{editing ? t("gpsMonitor.editDevice") : t("gpsMonitor.bindDevice")}</h2><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.deviceIdentifier")}</span><input required value={form.device_identifier} onChange={(e) => setForm({ ...form, device_identifier: e.target.value })} className={inputClass} /></label><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.protocol")}</span><select value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })} className={inputClass}><option value="sinotrack_h02">SinoTrack H02</option><option value="teltonika_avl">Teltonika AVL</option><option value="custom_http">{t("gpsMonitor.protocolHttp")}</option></select></label><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.vehicle")}</span><select required value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })} className={inputClass}><option value="">{t("gpsMonitor.notAssigned")}</option>{vehicles.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.registration_number}</option>)}</select></label><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.driver")}</span><select value={form.driver_user_id} onChange={(e) => setForm({ ...form, driver_user_id: e.target.value })} className={inputClass}><option value="">{t("gpsMonitor.notAssigned")}</option>{drivers.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.full_name || x.username}</option>)}</select></label><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.deviceStatus")}</span><select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={inputClass}><option value="active">{t("gpsMonitor.active")}</option><option value="inactive">{t("gpsMonitor.inactive")}</option></select></label><label className="space-y-1 text-sm font-semibold"><span>{t("gpsMonitor.notes")}</span><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className={inputClass} /></label><div className="flex justify-end gap-2 md:col-span-2"><button type="button" onClick={() => setShowForm(false)} className="rounded-xl border px-4 py-2 text-sm font-bold">{t("gpsMonitor.cancel")}</button><button disabled={busy} className="rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50" style={{ backgroundColor: "var(--brand-button)" }}>{busy ? t("gpsMonitor.saving") : t("gpsMonitor.save")}</button></div></form>}

    {loading && <div className={`${panel} text-center`}>{t("gpsMonitor.loading")}</div>}
    {!loading && !error && decorated.length === 0 && <div className={`${panel} text-center text-[var(--brand-muted)]`}>{t("gpsMonitor.noVehicles")}</div>}
    {!loading && decorated.length > 0 && <div className="grid min-w-0 gap-4 xl:grid-cols-[300px_minmax(420px,1fr)_340px]">
      <aside className={`${panel} min-w-0 space-y-3 xl:max-h-[640px] xl:overflow-y-auto`}><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("gpsMonitor.search")} className={inputClass} /><div className="flex flex-wrap gap-2">{FILTERS.map((key) => <button type="button" key={key} onClick={() => setFilter(key)} className={`rounded-full border px-2.5 py-1 text-xs font-bold ${filter === key ? "text-white" : ""}`} style={filter === key ? { backgroundColor: "var(--brand-button)" } : undefined}>{t(`gpsMonitor.filters.${key}`)}</button>)}</div><div className="space-y-2">{visible.map((item) => <button type="button" key={item.vehicle_id} onClick={() => setSelectedId(item.vehicle_id)} className={`w-full rounded-xl border p-3 text-left ${selectedId === item.vehicle_id ? "ring-2 ring-[var(--brand-primary)]" : ""}`}><div className="flex items-center justify-between gap-2"><strong>{item.registration_number}</strong><span className="flex items-center gap-1 text-xs"><i className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[item.status] || STATUS_DOT.no_signal}`} />{item.status_label}</span></div><p className="truncate text-sm">{item.driver_name || t("gpsMonitor.notAssigned")}</p><p className="mt-1 flex justify-between text-xs text-[var(--brand-muted)]"><span>{item.latest?.speed_kmh != null ? `${Number(item.latest.speed_kmh).toFixed(1)} km/h` : "—"}</span><span>{item.last_signal_label}</span></p></button>)}</div></aside>
      <main className="min-w-0 order-first xl:order-none"><FleetMap markers={decorated} route={history} selectedVehicleId={selectedId} onSelect={setSelectedId} labels={labels} height="clamp(380px, 62vh, 640px)" /><div className="mt-2 flex flex-wrap gap-3 text-xs">{["moving", "stopped", "waiting", "offline", "no_signal"].map((key) => <span className="flex items-center gap-1" key={key}><i className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[key]}`} />{t(`gpsMonitor.status.${key}`)}</span>)}</div></main>
      <aside className={`${panel} min-w-0`}>{!selected ? <p className="text-sm text-[var(--brand-muted)]">{t("gpsMonitor.selectVehicle")}</p> : <div className="space-y-5"><div><h2 className="text-xl font-black">{selected.registration_number}</h2><p className="text-sm text-[var(--brand-muted)]">{selected.vehicle_model || selected.vehicle_type || "—"}</p></div><Detail title={t("gpsMonitor.transport")} rows={[[t("gpsMonitor.state"), selected.status_label], [t("gpsMonitor.operationalState"), t(`gpsMonitor.vehicleStates.${String(selected.vehicle_operational_state || "unknown").toLowerCase()}`)], [t("gpsMonitor.deviceIdentifier"), selected.device_identifier], [t("gpsMonitor.protocol"), selected.device_protocol ? t(`gpsMonitor.protocols.${selected.device_protocol}`) : "—"], [t("gpsMonitor.deviceStatus"), selected.device_status ? t(`gpsMonitor.deviceStates.${selected.device_status}`) : t("gpsMonitor.unbound")]]} /><Detail title={t("gpsMonitor.driver")} rows={[[t("gpsMonitor.fullName"), selected.driver_name], [t("gpsMonitor.phone"), selected.driver_phone]]} /><Detail title={t("gpsMonitor.trip")} rows={[[t("gpsMonitor.tripNumber"), selected.trip_number], [t("gpsMonitor.origin"), selected.origin], [t("gpsMonitor.destination"), [selected.destination_city, selected.destination_site].filter(Boolean).join(" · ")], [t("gpsMonitor.tripStatus"), selected.trip_status ? t(`gpsMonitor.tripStatuses.${selected.trip_status}`) : "—"], [t("gpsMonitor.dispatchTime"), fmtDate(selected.actual_departure_at, locale)], [t("gpsMonitor.expectedArrival"), fmtDate(selected.delivery_deadline_at, locale)]]} />{selected.trip_id && <Link className="inline-flex rounded-xl border px-3 py-2 text-sm font-bold" to={`/logistics/shipments/${selected.trip_id}`}>{t("gpsMonitor.openTracking")}</Link>}<Detail title={t("gpsMonitor.liveGps")} rows={[[t("gpsMonitor.latitude"), selected.latest?.latitude?.toFixed?.(6) ?? selected.latest?.latitude], [t("gpsMonitor.longitude"), selected.latest?.longitude?.toFixed?.(6) ?? selected.latest?.longitude], [t("gpsMonitor.speed"), selected.latest?.speed_kmh != null ? `${Number(selected.latest.speed_kmh).toFixed(1)} km/h` : "—"], [t("gpsMonitor.heading"), selected.latest?.heading_deg], [t("gpsMonitor.captured"), fmtDate(selected.latest?.captured_at, locale)], [t("gpsMonitor.received"), fmtDate(selected.latest?.received_at, locale)], [t("gpsMonitor.lastSignal"), selected.last_signal_label]]} />{!selected.device_id && <StateCard text={t("gpsMonitor.deviceMissing")} action={() => openCreate(selected.vehicle_id)} label={t("gpsMonitor.bindDevice")} />}{selected.device_id && !selected.latest && <StateCard text={t("gpsMonitor.signalPending")} />}{history.length > 0 && <div><h3 className="font-black">{t("gpsMonitor.history")}</h3><div className="mt-2 max-h-40 space-y-2 overflow-y-auto">{history.slice(-10).reverse().map((point) => <div key={point.id} className="rounded-lg bg-[var(--brand-surface-muted)] p-2 text-xs"><strong>{fmtDate(point.captured_at, locale)}</strong><p>{point.speed_kmh != null ? `${Number(point.speed_kmh).toFixed(1)} km/h` : "—"} · {Number(point.latitude).toFixed(5)}, {Number(point.longitude).toFixed(5)}</p></div>)}</div></div>}</div>}</aside>
    </div>}
    {devices.length > 0 && <section className={`${panel}`}><h2 className="font-black">{t("gpsMonitor.registeredDevices")}</h2><div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{devices.map((device) => <article key={device.id} className="rounded-xl border p-3 text-sm"><strong>{device.device_identifier}</strong><p>{t(`gpsMonitor.protocols.${device.protocol || "custom_http"}`)}</p><div className="mt-2 flex gap-2"><button type="button" onClick={() => openEdit(device)} className="rounded-lg border px-2 py-1 font-bold">{t("gpsMonitor.edit")}</button><button type="button" disabled={busy || device.status !== "active"} onClick={() => unbind(device)} className="rounded-lg border px-2 py-1 font-bold disabled:opacity-50">{t("gpsMonitor.deactivate")}</button></div></article>)}</div></section>}
  </section>;
}

function Detail({ title, rows }) { return <div><h3 className="text-xs font-black uppercase tracking-wide text-[var(--brand-muted)]">{title}</h3><dl className="mt-2 space-y-1 text-sm">{rows.map(([label, value]) => <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-2" key={label}><dt className="text-[var(--brand-muted)]">{label}</dt><dd className="break-words font-semibold">{value || "—"}</dd></div>)}</dl></div>; }
function StateCard({ text, action, label }) { return <div className="rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700"><p>{text}</p>{action && <button type="button" onClick={action} className="mt-2 font-bold text-[var(--brand-primary)]">{label}</button>}</div>; }
