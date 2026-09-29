import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const EMPTY_ROW = { length_m: "", piece_count: "", unit_cost: "", price_basis: "PER_METER", warehouse_name: "", location_code: "", lot_number: "", notes: "" };
const initialForm = () => ({ material_id: "", receipt_number: "", received_at: new Date().toISOString().slice(0, 16), supplier_name: "", supplier_invoice: "", warehouse_name: "", location_code: "", lot_number: "", quantity: "", unit_cost: "", currency: "UZS", notes: "" });
const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const key = (prefix) => `${prefix}-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
const tone = (status) => status === "CONFIRMED" ? "bg-emerald-100 text-emerald-800" : ["REVERSED", "CANCELLED"].includes(status) ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800";

export default function MaterialsReceiptsPage() {
  const { hasPermission, isAdmin, user } = useAuth();
  const { t, locale } = useLocale();
  const canEdit = isAdmin || hasPermission("materials_edit");
  const [materials, setMaterials] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [rows, setRows] = useState([{ ...EMPTY_ROW }]);
  const [activeReceipt, setActiveReceipt] = useState(null);
  const [reverseReason, setReverseReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadSequence = useRef(0);
  const [toast, setToast] = useState("");
  const draftKey = useRef(""); const confirmKey = useRef(""); const reverseKey = useRef("");
  const material = useMemo(() => materials.find((row) => row.id === Number(form.material_id)), [materials, form.material_id]);
  const isProfile = material?.material_type === "PROFILE";
  const locked = Boolean(activeReceipt && activeReceipt.status !== "DRAFT");
  const kgPerMeter = number(material?.theoretical_weight_kg_per_m) || null;
  const calculatedRows = useMemo(() => rows.map((row) => {
    const length = number(row.length_m); const pieces = number(row.piece_count); const entered = number(row.unit_cost);
    const meters = length > 0 && pieces > 0 ? length * pieces : 0;
    const perMeter = row.price_basis === "PER_PIECE" && length > 0 ? entered / length : entered;
    return { ...row, total_meters: meters, price_per_meter: perMeter, row_total: row.price_basis === "PER_PIECE" ? pieces * entered : meters * entered, total_weight_kg: kgPerMeter == null ? null : meters * kgPerMeter };
  }), [rows, kgPerMeter]);
  const totals = useMemo(() => calculatedRows.reduce((acc, row) => ({ pieces: acc.pieces + number(row.piece_count), meters: acc.meters + row.total_meters, amount: acc.amount + row.row_total, weight: kgPerMeter == null ? null : (acc.weight || 0) + (row.total_weight_kg || 0) }), { pieces: 0, meters: 0, amount: 0, weight: kgPerMeter == null ? null : 0 }), [calculatedRows, kgPerMeter]);

  const load = useCallback(async () => {
    if (!canEdit) return;
    const sequence = ++loadSequence.current;
    setError("");
    try {
      const [items, history] = await Promise.all([api.materialsItems(), api.materialsReceipts()]);
      if (sequence !== loadSequence.current) return;
      setMaterials(items.materials || []);
      setReceipts(history.receipts || []);
    } catch (e) {
      if (sequence === loadSequence.current) setError(e.message);
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }, [canEdit]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setToast(""); }, [locale]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const updateRow = (index, field, value) => setRows((current) => current.map((row, i) => i === index ? { ...row, [field]: value } : row));
  const message = (e) => { const translated = e.code ? t(`materialReceipt.errors.${e.code}`) : ""; return translated && !translated.startsWith("materialReceipt.") ? translated : t("materialReceipt.errors.generic"); };
  const reset = () => { setForm(initialForm()); setRows([{ ...EMPTY_ROW }]); setActiveReceipt(null); setReverseReason(""); draftKey.current = ""; confirmKey.current = ""; reverseKey.current = ""; };
  const openReceipt = (receipt) => {
    setForm({ material_id: String(receipt.material_id), receipt_number: receipt.receipt_number || "", received_at: receipt.received_at ? new Date(receipt.received_at).toISOString().slice(0, 16) : "", supplier_name: receipt.supplier_name || "", supplier_invoice: receipt.supplier_invoice || "", warehouse_name: receipt.warehouse_name || "", location_code: receipt.location_code || "", lot_number: receipt.lot_number || "", quantity: String(receipt.quantity || ""), unit_cost: String(receipt.unit_cost || ""), currency: receipt.currency || "UZS", notes: receipt.notes || "" });
    setRows(receipt.profile_rows?.length ? receipt.profile_rows.map((row) => ({ ...EMPTY_ROW, ...row, length_m: String(row.length_m), piece_count: String(row.piece_count), unit_cost: String(row.entered_cost ?? row.unit_cost ?? "") })) : [{ ...EMPTY_ROW }]);
    setActiveReceipt(receipt); setReverseReason(""); draftKey.current = receipt.operation_key || ""; confirmKey.current = ""; reverseKey.current = "";
    document.querySelector("main")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const validRows = calculatedRows.length > 0 && calculatedRows.every((row) => number(row.length_m) > 0 && Number.isInteger(number(row.piece_count)) && number(row.piece_count) > 0 && number(row.unit_cost) >= 0 && (row.warehouse_name || form.warehouse_name).trim() && (row.location_code || form.location_code).trim());
  const canSubmit = Boolean(form.material_id) && (isProfile ? validRows : number(form.quantity) > 0);
  const payload = (confirm) => ({ material_id: Number(form.material_id), receipt_number: form.receipt_number.trim(), received_at: form.received_at ? new Date(form.received_at).toISOString() : null, supplier_name: form.supplier_name.trim(), supplier_invoice: form.supplier_invoice.trim(), warehouse_name: form.warehouse_name.trim(), location_code: form.location_code.trim(), lot_number: form.lot_number.trim(), currency: form.currency, notes: form.notes.trim(), reference: form.supplier_invoice.trim() || form.receipt_number.trim(), quantity: isProfile ? totals.meters : number(form.quantity), unit_cost: isProfile ? null : number(form.unit_cost), price_basis: isProfile ? calculatedRows[0]?.price_basis || "PER_METER" : "PER_UNIT", profile_rows: isProfile ? calculatedRows.map((row) => ({ length_m: number(row.length_m), piece_count: number(row.piece_count), unit_cost: number(row.unit_cost), price_basis: row.price_basis, warehouse_name: (row.warehouse_name || form.warehouse_name).trim(), location_code: (row.location_code || form.location_code).trim(), lot_number: (row.lot_number || form.lot_number).trim(), notes: row.notes.trim() })) : [], operation_key: draftKey.current, confirm });

  const saveDraft = async () => {
    if (!canSubmit || busy || locked) return; draftKey.current ||= key("receipt-draft"); setBusy(true); setToast("");
    try { const saved = activeReceipt?.status === "DRAFT" ? await api.materialsUpdateReceipt(activeReceipt.id, { ...payload(false), expected_version: activeReceipt.version }) : await api.materialsCreateReceipt(payload(false)); setActiveReceipt(saved); await load(); setToast(t("materialReceipt.draftSaved")); }
    catch (e) { setToast(message(e)); } finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!canSubmit || busy) return; setBusy(true); setToast("");
    try { let saved = activeReceipt; if (!saved) { draftKey.current ||= key("receipt-create"); saved = await api.materialsCreateReceipt(payload(false)); } confirmKey.current ||= key("receipt-confirm"); const confirmed = await api.materialsConfirmReceipt(saved.id, { operation_key: confirmKey.current }); setActiveReceipt(confirmed); await load(); setToast(t("materialReceipt.confirmed")); }
    catch (e) { setToast(message(e)); } finally { setBusy(false); }
  };
  const reverse = async () => {
    if (!activeReceipt || !reverseReason.trim() || busy) return; reverseKey.current ||= key("receipt-reverse"); setBusy(true); setToast("");
    try { const reversed = await api.materialsReverseReceipt(activeReceipt.id, { operation_key: reverseKey.current, reason: reverseReason.trim() }); setActiveReceipt(reversed); await load(); setToast(t("materialReceipt.reversed")); }
    catch (e) { setToast(message(e)); } finally { setBusy(false); }
  };
  if (!canEdit) return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;

  return <div className="pb-24">
    <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">← {t("materials.title")}</Link>
    <PageHeader title={t("materials.receiptsTitle")} subtitle={t("materialReceipt.subtitle")} />
    {loading ? <LoadingSpinner /> : null}<ErrorAlert message={error} onRetry={load} />
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <section className="overflow-hidden rounded-2xl border border-blue-100 bg-[var(--brand-card)] shadow-sm">
        <div className="bg-[var(--brand-primary)] px-5 py-4 text-white"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-100">{t("materialReceipt.document")}</p><h2 className="text-xl font-black">{form.receipt_number || t("materialReceipt.newDocument")}</h2></div><span className={`rounded-full px-3 py-1 text-xs font-black ${tone(activeReceipt?.status || "DRAFT")}`}>{t(`materialReceipt.status.${activeReceipt?.status || "DRAFT"}`)}</span></div></div>
        <div className="space-y-5 p-4 sm:p-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Field label={t("materialReceipt.receiptNumber")}><input value={form.receipt_number} onChange={(e) => update("receipt_number", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.receivedAt")}><input type="datetime-local" value={form.received_at} onChange={(e) => update("received_at", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.supplier")}><input value={form.supplier_name} onChange={(e) => update("supplier_name", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.supplierInvoice")}><input value={form.supplier_invoice} onChange={(e) => update("supplier_invoice", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.warehouse")}><input value={form.warehouse_name} onChange={(e) => update("warehouse_name", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.location")}><input value={form.location_code} onChange={(e) => update("location_code", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.lot")}><input value={form.lot_number} onChange={(e) => update("lot_number", e.target.value)} disabled={busy || locked} /></Field>
            <Field label={t("materialReceipt.currency")}><select value={form.currency} onChange={(e) => update("currency", e.target.value)} disabled={busy || locked}><option value="UZS">UZS</option><option value="USD">USD</option><option value="RUB">RUB</option></select></Field>
          </div>
          <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4"><label className="block text-xs font-black uppercase tracking-wide text-blue-900">{t("materialReceipt.material")}</label><select value={form.material_id} onChange={(e) => { update("material_id", e.target.value); setRows([{ ...EMPTY_ROW }]); }} disabled={busy || locked} className="mt-2 min-h-[48px] w-full rounded-xl border border-blue-200 bg-white px-3 font-semibold"><option value="">{t("materials.selectMaterial")}</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select>{material ? <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5"><Meta label={t("materialReceipt.category")} value={material.category_name} /><Meta label={t("materialReceipt.specification")} value={[material.width_mm, material.height_mm, material.thickness_mm].filter(Boolean).join(" × ") || material.profile_type} /><Meta label={t("materialReceipt.baseUnit")} value={material.base_unit} /><Meta label={t("materialReceipt.purchaseUnit")} value={material.purchase_unit} /><Meta label={t("materialReceipt.responsible")} value={user?.full_name || user?.username} /></dl> : null}</div>
          {isProfile ? <ProfileRows rows={rows} calculatedRows={calculatedRows} form={form} kgPerMeter={kgPerMeter} locked={locked} busy={busy} t={t} setRows={setRows} updateRow={updateRow} /> : material ? <div className="grid gap-3 sm:grid-cols-2"><Field label={t("materials.fieldQuantity")}><input type="number" min="0.001" step="any" value={form.quantity} onChange={(e) => update("quantity", e.target.value)} disabled={busy || locked} /></Field><Field label={t("materials.fieldUnitCostOptional")}><input type="number" min="0" step="any" value={form.unit_cost} onChange={(e) => update("unit_cost", e.target.value)} disabled={busy || locked} /></Field></div> : null}
          <Field label={t("common.notes")}><textarea rows={3} value={form.notes} onChange={(e) => update("notes", e.target.value)} disabled={busy || locked} /></Field>
          <div className="flex flex-wrap justify-end gap-3 border-t pt-4"><button type="button" onClick={reset} disabled={busy} className="min-h-[46px] rounded-xl border px-5 font-bold">{t("common.clear")}</button><button type="button" onClick={saveDraft} disabled={busy || !canSubmit || locked} className="min-h-[46px] rounded-xl border border-blue-300 px-5 font-bold text-blue-800 disabled:opacity-50">{t("materialReceipt.saveDraft")}</button><button type="button" onClick={confirm} disabled={busy || !canSubmit || ["CONFIRMED", "REVERSED", "CANCELLED"].includes(activeReceipt?.status)} className="min-h-[46px] rounded-xl bg-[var(--brand-button)] px-6 font-black text-white disabled:opacity-50">{busy ? t("common.saving") : t("materialReceipt.confirm")}</button></div>
          {activeReceipt?.status === "CONFIRMED" ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-4"><label className="block text-sm font-bold text-rose-900">{t("materialReceipt.reversalReason")}<textarea rows={2} value={reverseReason} onChange={(e) => setReverseReason(e.target.value)} className="mt-1 w-full rounded-lg border border-rose-200 bg-white px-3 py-2" /></label><button type="button" onClick={reverse} disabled={busy || !reverseReason.trim()} className="mt-3 min-h-[44px] rounded-xl bg-rose-700 px-5 font-bold text-white disabled:opacity-50">{t("materialReceipt.reverse")}</button></div> : null}
        </div>
      </section>
      <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start"><div className="rounded-2xl border border-blue-100 bg-[var(--brand-card)] p-5 shadow-sm"><h3 className="text-sm font-black uppercase tracking-wider text-blue-900">{t("materialReceipt.summary")}</h3><dl className="mt-4 space-y-3"><Summary label={t("materialReceipt.material")} value={material ? `${material.code} — ${material.name}` : "—"} /><Summary label={t("materialReceipt.totalPieces")} value={isProfile ? totals.pieces.toLocaleString() : "—"} /><Summary label={t("materialReceipt.totalMeters")} value={isProfile ? `${totals.meters.toLocaleString()} m` : `${number(form.quantity).toLocaleString()} ${material?.base_unit || ""}`} /><Summary label={t("materialReceipt.totalKg")} value={totals.weight == null ? "—" : `${totals.weight.toLocaleString()} kg`} /><Summary label={t("materialReceipt.totalAmount")} value={`${(isProfile ? totals.amount : number(form.quantity) * number(form.unit_cost)).toLocaleString()} ${form.currency}`} /><Summary label={t("materialReceipt.supplier")} value={form.supplier_name || "—"} /><Summary label={t("materialReceipt.warehouse")} value={form.warehouse_name || "—"} /><Summary label={t("materialReceipt.statusLabel")} value={t(`materialReceipt.status.${activeReceipt?.status || "DRAFT"}`)} /></dl></div></aside>
    </div>
    <h3 className="mb-3 mt-8 font-black">{t("materials.recentReceipts")}</h3><div className="grid gap-3 lg:grid-cols-2">{receipts.map((receipt) => <article key={receipt.id} className="rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="font-black">{receipt.receipt_number}</p><p className="text-sm">{receipt.material_code} — {receipt.material_name}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-black ${tone(receipt.status)}`}>{t(`materialReceipt.status.${receipt.status}`)}</span></div><p className="mt-3 text-sm font-semibold">{receipt.total_pieces ? `${receipt.total_pieces} ${t("materialMaster.units.pcs")} · ` : ""}{receipt.quantity} {receipt.base_unit} · {receipt.total_amount?.toLocaleString()} {receipt.currency}</p><p className="mt-1 text-xs text-[var(--brand-muted)]">{receipt.supplier_name || "—"} · {receipt.warehouse_name || "—"} · {receipt.received_at ? new Date(receipt.received_at).toLocaleString(locale === "ru" ? "ru-RU" : "uz-UZ") : "—"}</p>{receipt.length_lots?.length ? <div className="mt-2 flex flex-wrap gap-1">{receipt.length_lots.map((lot) => <span key={lot.id} className="rounded-lg bg-blue-50 px-2 py-1 text-xs font-bold text-blue-800">{lot.length_m} m × {lot.pieces_received || lot.pieces_on_hand}</span>)}</div> : null}<button type="button" onClick={() => openReceipt(receipt)} className="mt-3 min-h-[40px] rounded-lg border border-blue-200 px-3 text-sm font-bold text-blue-800">{t("materialReceipt.open")}</button></article>)}</div>
    <Toast message={toast} onClose={() => setToast("")} />
  </div>;
}

function ProfileRows({ rows, calculatedRows, form, kgPerMeter, locked, busy, t, setRows, updateRow }) {
  return <div className="space-y-3"><div className="flex items-center justify-between gap-3"><h3 className="font-black text-slate-900">{t("materialReceipt.physicalRows")}</h3><button type="button" onClick={() => setRows((current) => [...current, { ...EMPTY_ROW }])} disabled={busy || locked} className="min-h-[42px] rounded-xl border border-blue-200 px-3 text-sm font-bold text-blue-800 disabled:opacity-50">+ {t("materialReceipt.addRow")}</button></div><div className="overflow-x-auto rounded-xl border border-slate-200"><table className="min-w-[1400px] w-full text-left text-xs"><thead className="bg-slate-900 text-white"><tr>{["length", "pieces", "totalMeters", "priceBasis", "enteredPrice", "pricePerMeter", "rowAmount", "kgPerMeter", "totalKg", "warehouse", "location", "lot", "notes", "action"].map((name) => <th key={name} className="px-2 py-3 font-bold">{t(`materialReceipt.${name}`)}</th>)}</tr></thead><tbody>{calculatedRows.map((row, index) => <tr key={index} className="border-t align-top"><InputCell type="number" value={row.length_m} onChange={(value) => updateRow(index, "length_m", value)} disabled={busy || locked} /><InputCell type="number" value={row.piece_count} onChange={(value) => updateRow(index, "piece_count", value)} disabled={busy || locked} /><ValueCell value={`${row.total_meters.toLocaleString()} m`} /><td className="p-2"><select value={row.price_basis} onChange={(e) => updateRow(index, "price_basis", e.target.value)} disabled={busy || locked} className="min-h-[40px] rounded-lg border px-2"><option value="PER_METER">{t("materialReceipt.perMeter")}</option><option value="PER_PIECE">{t("materialReceipt.perPiece")}</option></select></td><InputCell type="number" value={row.unit_cost} onChange={(value) => updateRow(index, "unit_cost", value)} disabled={busy || locked} /><ValueCell value={row.price_per_meter.toLocaleString()} /><ValueCell value={row.row_total.toLocaleString()} /><ValueCell value={kgPerMeter == null ? "—" : kgPerMeter.toLocaleString()} /><ValueCell value={row.total_weight_kg == null ? "—" : row.total_weight_kg.toLocaleString()} /><InputCell value={row.warehouse_name} placeholder={form.warehouse_name} onChange={(value) => updateRow(index, "warehouse_name", value)} disabled={busy || locked} /><InputCell value={row.location_code} placeholder={form.location_code} onChange={(value) => updateRow(index, "location_code", value)} disabled={busy || locked} /><InputCell value={row.lot_number} placeholder={form.lot_number} onChange={(value) => updateRow(index, "lot_number", value)} disabled={busy || locked} /><InputCell value={row.notes} onChange={(value) => updateRow(index, "notes", value)} disabled={busy || locked} /><td className="p-2"><button type="button" onClick={() => setRows((current) => current.filter((_, i) => i !== index))} disabled={busy || locked || rows.length === 1} className="min-h-[40px] rounded-lg px-3 font-bold text-rose-700 disabled:opacity-40">{t("common.remove")}</button></td></tr>)}</tbody></table></div></div>;
}
function Field({ label, children }) { return <label className="block text-sm font-bold text-slate-700"><span>{label}</span><span className="mt-1 block [&>input]:min-h-[46px] [&>input]:w-full [&>input]:rounded-xl [&>input]:border [&>input]:px-3 [&>select]:min-h-[46px] [&>select]:w-full [&>select]:rounded-xl [&>select]:border [&>select]:px-3 [&>textarea]:w-full [&>textarea]:rounded-xl [&>textarea]:border [&>textarea]:px-3 [&>textarea]:py-2">{children}</span></label>; }
function Meta({ label, value }) { return <div><dt className="text-xs font-bold text-slate-500">{label}</dt><dd className="font-semibold text-slate-900">{value || "—"}</dd></div>; }
function Summary({ label, value }) { return <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2"><dt className="text-xs font-bold text-slate-500">{label}</dt><dd className="text-right text-sm font-black text-slate-900">{value}</dd></div>; }
function ValueCell({ value }) { return <td className="whitespace-nowrap p-2 font-bold text-slate-700">{value}</td>; }
function InputCell({ value, onChange, type = "text", placeholder = "", disabled }) { return <td className="p-2"><input type={type} min={type === "number" ? "0" : undefined} step={type === "number" ? "any" : undefined} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} disabled={disabled} className="min-h-[40px] w-[96px] rounded-lg border px-2 disabled:bg-slate-50" /></td>; }
