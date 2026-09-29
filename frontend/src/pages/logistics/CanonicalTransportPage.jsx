import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import LogisticsSectionNav from "../../components/logistics/LogisticsSectionNav";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage, date, panel } from "../productionProjects/projectUi";

const activeStatuses = ["planned", "loading", "loaded", "dispatched", "in_transit"];
const emptyForm = { vehicle_type: "", registration_number: "", internal_code: "", model: "", max_payload_kg: "", internal_length_mm: "", internal_width_mm: "", internal_height_mm: "", max_volume_m3: "", notes: "", is_active: true };
const inputClass = "w-full rounded-xl border border-[var(--brand-border)] bg-[var(--brand-surface)] px-3 py-2 text-sm";
const vehicleLabels = { registration_number: "checkpointD.fields.registration_number", internal_code: "logisticsCenter.masterData.internalCode", vehicle_type: "checkpointD.fields.vehicle_type", model: "logisticsCenter.masterData.model", max_payload_kg: "checkpointD.fields.max_payload_kg", internal_length_mm: "checkpointD.fields.internal_length_mm", internal_width_mm: "checkpointD.fields.internal_width_mm", internal_height_mm: "checkpointD.fields.internal_height_mm", max_volume_m3: "checkpointD.fields.max_volume_m3" };

export default function CanonicalTransportPage() {
  const { t, locale } = useLocale();
  const [rows, setRows] = useState([]), [fleet, setFleet] = useState([]), [trips, setTrips] = useState([]);
  const [busy, setBusy] = useState(true), [saving, setSaving] = useState(false), [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm), [editing, setEditing] = useState(null), [showForm, setShowForm] = useState(false);
  const load = useCallback(async () => {
    setBusy(true);
    try { const [a, b, c] = await Promise.all([api.finishedVehicles(true), api.finishedTrackingFleet(), api.finishedTrips()]); setRows(a.vehicles || []); setFleet(b.items || []); setTrips(c.trips || []); setError(""); }
    catch (e) { setError(apiMessage(e, t)); }
    finally { setBusy(false); }
  }, [t]);
  useEffect(() => { load(); }, [load]);
  const openCreate = () => { setEditing(null); setForm({ ...emptyForm }); setShowForm(true); setError(""); };
  const openEdit = (vehicle) => { setEditing(vehicle); setForm({ ...emptyForm, ...vehicle, max_payload_kg: vehicle.max_payload_kg ?? vehicle.load_capacity ?? "", is_active: vehicle.is_active !== false }); setShowForm(true); setError(""); };
  const change = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const numeric = (value) => value === "" || value == null ? undefined : Number(value);
  const save = async (event) => {
    event.preventDefault(); setSaving(true); setError("");
    const body = { ...form, max_payload_kg: numeric(form.max_payload_kg), internal_length_mm: numeric(form.internal_length_mm), internal_width_mm: numeric(form.internal_width_mm), internal_height_mm: numeric(form.internal_height_mm), max_volume_m3: numeric(form.max_volume_m3) };
    try { if (editing) await api.finishedVehicleUpdate(editing.id, { ...body, expected_version: editing.version }); else await api.finishedVehicleCreate(body); setShowForm(false); setEditing(null); await load(); }
    catch (e) { setError(apiMessage(e, t)); }
    finally { setSaving(false); }
  };
  const setState = async (vehicle, operational_state) => { setSaving(true); setError(""); try { await api.finishedVehicleStateUpdate(vehicle.id, { expected_version: vehicle.version, operational_state }); await load(); } catch (e) { setError(apiMessage(e, t)); } finally { setSaving(false); } };
  const activeTrips = useMemo(() => trips.filter((trip) => activeStatuses.includes(trip.status)), [trips]);
  return <section className="space-y-4">
    <LogisticsSectionNav />
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-black">{t("logisticsCenter.transport.title")}</h1><p className="text-sm text-[var(--brand-muted)]">{t("logisticsCenter.transport.subtitle")}</p></div><button type="button" onClick={openCreate} className="rounded-xl px-4 py-2 text-sm font-bold text-white" style={{ backgroundColor: "var(--brand-button)" }}>{t("logisticsCenter.masterData.addVehicle")}</button></header>
    {error && <ErrorAlert message={error} onRetry={load} />}
    {showForm && <form onSubmit={save} className={`${panel} grid gap-3 md:grid-cols-2`}><h2 className="text-lg font-black md:col-span-2">{editing ? t("logisticsCenter.masterData.editVehicle") : t("logisticsCenter.masterData.addVehicle")}</h2>{Object.keys(vehicleLabels).map((field) => <label key={field} className="space-y-1 text-sm font-semibold"><span>{t(vehicleLabels[field])}</span><input required={["registration_number", "vehicle_type", "max_payload_kg", "internal_length_mm", "internal_width_mm", "internal_height_mm"].includes(field)} type={field.includes("mm") || field.includes("payload") || field.includes("volume") ? "number" : "text"} min={field.includes("mm") || field.includes("payload") || field.includes("volume") ? "0.01" : undefined} step="any" value={form[field] ?? ""} onChange={(event) => change(field, event.target.value)} className={inputClass} /></label>)}<label className="space-y-1 text-sm font-semibold md:col-span-2"><span>{t("logisticsCenter.masterData.notes")}</span><textarea value={form.notes} onChange={(event) => change("notes", event.target.value)} className={inputClass} rows={2} /></label><label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={form.is_active} onChange={(event) => change("is_active", event.target.checked)} />{t("logisticsCenter.masterData.active")}</label><div className="flex flex-wrap justify-end gap-2 md:col-span-2"><button type="button" onClick={() => setShowForm(false)} className="rounded-xl border px-4 py-2 text-sm font-bold">{t("logisticsCenter.masterData.cancel")}</button><button disabled={saving} type="submit" className="rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50" style={{ backgroundColor: "var(--brand-button)" }}>{saving ? t("checkpointD.actions.loading") : t("logisticsCenter.masterData.saveVehicle")}</button></div></form>}
    {busy ? <LoadingSpinner /> : rows.length === 0 ? <div className={`${panel} text-center`}><p className="mb-3 text-sm text-[var(--brand-muted)]">{t("logisticsCenter.masterData.noVehicles")}</p><button type="button" onClick={openCreate} className="rounded-xl px-4 py-2 text-sm font-bold text-white" style={{ backgroundColor: "var(--brand-button)" }}>{t("logisticsCenter.masterData.addVehicle")}</button></div> : <div className="grid min-w-0 gap-3 md:grid-cols-2">{rows.map((vehicle) => { const trip = activeTrips.find((item) => item.vehicle_id === vehicle.id); const live = fleet.find((item) => item.vehicle_id === vehicle.id); const state = vehicle.operational_state === "INACTIVE" ? "inactive" : vehicle.operational_state === "SERVICE" ? "service" : trip && ["dispatched", "in_transit"].includes(trip.status) ? "inTransit" : trip?.status === "loading" ? "loading" : trip ? "assigned" : "available"; return <article className={panel} key={vehicle.id}><div className="flex justify-between gap-2"><strong>{vehicle.registration_number}</strong><span className="rounded-full border px-2 py-1 text-xs font-bold">{t(`logisticsCenter.transport.states.${state}`)}</span></div><p>{vehicle.vehicle_type}{vehicle.model ? ` · ${vehicle.model}` : ""} · {vehicle.max_payload_kg} kg</p>{vehicle.internal_code && <p className="text-xs text-[var(--brand-muted)]">{t("logisticsCenter.masterData.internalCode")}: {vehicle.internal_code}</p>}<p className="text-sm">{t("checkpointD.tracking.trip")}: {trip ? <Link className="font-bold hover:underline" to={`/logistics/shipments/${trip.id}`}>{trip.trip_number}</Link> : t("logisticsCenter.masterData.noAssignment")}</p><p className="text-sm">{t("checkpointD.fields.driver")}: {trip?.driver_name_snapshot || live?.driver_name || t("logisticsCenter.masterData.noAssignment")}</p><p className="text-sm text-[var(--brand-muted)]">{t("logisticsCenter.masterData.gps")}: {live ? t(`checkpointD.tracking.health.${live.status}`) : t("checkpointD.tracking.health.offline")} · {date(live?.last_contact_at, locale)}</p>{live?.device_identifier && <p className="text-xs text-[var(--brand-muted)]">{t("logisticsCenter.masterData.deviceId")}: {live.device_identifier}</p>}<div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => openEdit(vehicle)} className="rounded-xl border px-3 py-2 text-sm font-bold">{t("logisticsCenter.masterData.edit")}</button>{["AVAILABLE", "SERVICE", "INACTIVE"].map((value) => <button type="button" key={value} disabled={saving || !!trip || vehicle.operational_state === value} onClick={() => setState(vehicle, value)} className="rounded-xl border px-3 py-2 text-sm font-bold disabled:opacity-50">{t(`logisticsCenter.transport.persistent.${value}`)}</button>)}</div>{trip && <p className="mt-2 text-xs text-[var(--brand-muted)]">{t("logisticsCenter.transport.activeTripLock")}</p>}</article>; })}</div>}
  </section>;
}
