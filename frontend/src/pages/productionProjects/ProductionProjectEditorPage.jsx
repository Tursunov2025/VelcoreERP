import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import { apiMessage, button, field, idempotency, number, panel } from "./projectUi";

const empty = { project_code:"", project_name:"", customer_name_snapshot:"", destination_region:"", destination_city:"", site_name:"", full_address:"", required_delivery_date:"", priority:"normal", notes:"" };
export default function ProductionProjectEditorPage() {
  const { id } = useParams(); const edit = Boolean(id); const { t, locale } = useLocale(); const { hasPermission } = useAuth(); const nav = useNavigate();
  const [project, setProject] = useState(null); const [form, setForm] = useState(empty); const [templates, setTemplates] = useState([]); const [newLine, setNewLine] = useState({ product_id:"", quantity:1 }); const [preview, setPreview] = useState(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [dirty, setDirty] = useState(false); const [lineDirty, setLineDirty] = useState(false); const [confirm, setConfirm] = useState(null); const releaseKey = useRef(null); const previewRequest = useRef(null); const savePromise = useRef(null); const navigationAllowed = useRef(false); const pendingBaseQuantity = useRef(0);
  const load = async () => { if (!edit) return; try { const p = await api.productionProject(id); setProject(p); setForm({ ...empty, ...p, required_delivery_date: p.required_delivery_date?.slice(0,16) || "" }); setDirty(false); } catch(e) { setError(apiMessage(e,t)); } };
  useEffect(() => { load(); api.mesGetTemplates().then(d => setTemplates(d.items || d.templates || d || [])).catch(() => setTemplates([])); return () => previewRequest.current?.abort(); }, [id]);
  const hasUnsaved = dirty || lineDirty;
  useEffect(() => { const guard = e => { if (hasUnsaved) { e.preventDefault(); e.returnValue = ""; } }; addEventListener("beforeunload", guard); return () => removeEventListener("beforeunload", guard); }, [hasUnsaved]);
  useEffect(() => {
    const guardLink = event => {
      if (!hasUnsaved || navigationAllowed.current || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest?.("a[href]");
      if (!anchor || anchor.target === "_blank") return;
      const target = new URL(anchor.href, globalThis.location.href);
      if (target.origin !== globalThis.location.origin) return;
      event.preventDefault();
      if (globalThis.confirm(t("checkpointD.editor.unsavedWarning"))) { navigationAllowed.current = true; nav(`${target.pathname}${target.search}${target.hash}`); }
    };
    document.addEventListener("click", guardLink, true);
    return () => document.removeEventListener("click", guardLink, true);
  }, [hasUnsaved, nav, t]);
  const change = (key, value) => { setForm({ ...form, [key]: value }); setDirty(true); };
  const persistPendingLine = async (base) => {
    if (!lineDirty || !newLine.product_id) return base;
    const quantity = Number(newLine.quantity); const productId = Number(newLine.product_id);
    if (!(quantity > 0)) throw Object.assign(new Error("invalid line"), { code:"invalid_product_line" });
    const targetQuantity = pendingBaseQuantity.current + quantity;
    let current = await api.productionProject(base.id);
    const existing = (current.lines || []).find(x => x.product_id === productId);
    const recorded = Number(existing?.quantity || 0);
    if (recorded < targetQuantity) {
      if (existing) await api.productionProjectMergeLine(current.id, { product_id:productId, additional_quantity:targetQuantity-recorded, expected_project_version:current.version });
      else await api.productionProjectAddLine(current.id, { product_id:productId, quantity:targetQuantity });
      current = await api.productionProject(base.id);
    }
    const refreshed = current;
    const persisted = refreshed.lines?.find(x => x.product_id === productId && x.id);
    if (!persisted || Number(persisted.quantity) < targetQuantity) throw Object.assign(new Error("line confirmation failed"), { code:"project_line_not_persisted" });
    return refreshed;
  };
  const save = async (targetStatus) => {
    if (savePromise.current) return savePromise.current;
    const task = (async () => { setBusy(true); setError(""); try {
      let result;
      if (edit) result = await api.productionProjectUpdate(id, { ...form, project_code: undefined, expected_version: project.version, status:project.status, required_delivery_date: form.required_delivery_date || null });
      else result = await api.productionProjectCreate({ ...form, required_delivery_date: form.required_delivery_date || null });
      // Header persistence may succeed even if the following line request fails.
      // Retain its authoritative version so a retry can continue instead of
      // producing a false optimistic-lock conflict; entered line data stays intact.
      setProject(current => ({ ...(current || {}), ...result }));
      result = await persistPendingLine(result);
      if (targetStatus && targetStatus !== result.status) {
        if (!(result.lines || []).length) throw Object.assign(new Error("project has no lines"), { code:"project_has_no_lines" });
        result = await api.productionProjectUpdate(result.id, { expected_version:result.version, status:targetStatus });
      }
      const confirmed = await api.productionProject(result.id);
      setProject(confirmed); setForm({ ...empty, ...confirmed, required_delivery_date: confirmed.required_delivery_date?.slice(0,16) || "" });
      setDirty(false); setLineDirty(false); setNewLine({ product_id:"", quantity:1 }); pendingBaseQuantity.current = 0;
      if (!edit) { navigationAllowed.current = true; nav(`/production-projects/${confirmed.id}/edit`, { replace:true }); }
      return confirmed;
    } catch(e) { setError(apiMessage(e,t)); return null; } finally { setBusy(false); savePromise.current = null; } })();
    savePromise.current = task; return task;
  };
  const addLine = async () => { if (!newLine.product_id || !(Number(newLine.quantity) > 0)) return; try { await save(); } catch {} };
  const doPreview = async () => { previewRequest.current?.abort(); const controller = new AbortController(); previewRequest.current = controller; setError(""); try { const result = await api.productionProjectPreview(project.id, controller.signal); if (previewRequest.current === controller) setPreview(result); } catch(e) { if (previewRequest.current === controller) { const message=apiMessage(e,t); if(message)setError(message); } } finally { if (previewRequest.current === controller) previewRequest.current = null; } };
  const release = async () => { if (busy || hasUnsaved || !(project?.lines || []).length) return; setConfirm(null); setBusy(true); releaseKey.current ||= idempotency(`release-${project.id}`); try { const current = await api.productionProject(project.id); if (!(current.lines || []).length) throw Object.assign(new Error("project has no lines"), { code:"project_has_no_lines" }); const r = await api.productionProjectRelease(project.id, { expected_version:current.version, idempotency_key:releaseKey.current }); setProject(r.project); releaseKey.current = null; } catch(e) { setError(apiMessage(e,t)); } finally { setBusy(false); } };
  const locked = project && !["draft","planned"].includes(project.status); const canEdit = hasPermission("production_projects_edit") && !locked;
  const lineInvalid = lineDirty && (!newLine.product_id || !(Number(newLine.quantity) > 0));
  const releaseDisabled = busy || hasUnsaved || lineInvalid || !(project?.lines || []).length;
  const releaseHint = !(project?.lines || []).length ? t("checkpointD.editor.releaseNeedsLine") : lineInvalid ? t("checkpointD.editor.invalidLine") : hasUnsaved ? t("checkpointD.editor.saveBeforeRelease") : "";
  return <section className="space-y-4"><header><h1 className="text-2xl font-black">{edit ? t("checkpointD.editor.editTitle") : t("checkpointD.editor.createTitle")}</h1>{locked && <p className="mt-1 text-amber-600">{t("checkpointD.editor.readOnly")}</p>}</header>{error && <ErrorAlert message={error} onRetry={load}/>}<div className={`${panel} grid gap-4 md:grid-cols-2`}>{Object.entries({project_code:"text",project_name:"text",customer_name_snapshot:"text",destination_region:"text",destination_city:"text",site_name:"text",full_address:"text",required_delivery_date:"datetime-local"}).map(([key,type]) => <label key={key} className={key === "full_address" ? "md:col-span-2" : ""}><span className="mb-1 block text-sm font-semibold">{t(`checkpointD.fields.${key}`)}</span><input className={field} type={type} value={form[key] || ""} disabled={locked || (edit && key === "project_code")} onChange={e => change(key,e.target.value)} required={["project_code","project_name","customer_name_snapshot"].includes(key)}/></label>)}<label><span className="mb-1 block text-sm font-semibold">{t("checkpointD.fields.priority")}</span><select className={field} value={form.priority} disabled={locked} onChange={e => change("priority",e.target.value)}>{["low","normal","high","urgent"].map(x => <option key={x} value={x}>{t(`checkpointD.priority.${x}`)}</option>)}</select></label><label className="md:col-span-2"><span className="mb-1 block text-sm font-semibold">{t("checkpointD.fields.notes")}</span><textarea className={field} rows="3" value={form.notes || ""} disabled={locked} onChange={e => change("notes",e.target.value)}/></label></div>
  {project && <div className={panel}><h2 className="text-lg font-black">{t("checkpointD.editor.lines")}</h2>{canEdit && <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_150px_auto]"><select className={field} value={newLine.product_id} onChange={e => { const productId=Number(e.target.value); pendingBaseQuantity.current=Number((project.lines||[]).find(x=>x.product_id===productId)?.quantity||0); setNewLine({...newLine,product_id:e.target.value}); setLineDirty(Boolean(e.target.value)); }}><option value="">{t("checkpointD.editor.selectTemplate")}</option>{templates.map(x => <option key={x.id} value={x.id}>{x.code} — {x.name} {x.revision ? `(${x.revision})` : ""}</option>)}</select><input className={field} type="number" min="0.01" step="0.01" value={newLine.quantity} onChange={e => { setNewLine({...newLine,quantity:e.target.value}); if (newLine.product_id) setLineDirty(true); }}/><button className={`${button} brand-btn brand-btn-primary`} onClick={addLine} disabled={busy || lineInvalid}>{t("checkpointD.actions.add")}</button></div>}{lineDirty && <p className="mt-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 dark:bg-amber-950 dark:text-amber-100">{t("checkpointD.editor.unsavedLine")}</p>}<div className="mt-3 space-y-2">{(project.lines || []).map(line => <div key={line.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3"><span><strong>{line.product_code}</strong> · {line.product_name}</span><span>{number(line.quantity,locale)} · {t("checkpointD.editor.savedLine")}</span>{canEdit && <button className="text-red-600" onClick={async()=>{await api.productionProjectRemoveLine(project.id,line.id);load();}}>{t("checkpointD.actions.remove")}</button>}</div>)}</div><div className="mt-3 text-right font-bold">{t("checkpointD.fields.total")}: {number((project.lines||[]).reduce((s,x)=>s+Number(x.quantity),0),locale)}</div></div>}
  {preview && <div className={panel}><h2 className="font-black">{t("checkpointD.editor.requirements")}</h2><div className="mt-2 grid gap-2 sm:grid-cols-2">{(preview.requirements || Object.values(preview.totals || {})).map((r,i)=><div key={r.detail_id || i} className="rounded-xl border p-3"><strong>{r.detail_code || r.code}</strong><p>{t("checkpointD.editor.stockCovered")}: {number(r.stock_reserved_quantity || r.stock_covered_quantity,locale)}</p><p>{t("checkpointD.editor.productionRequired")}: {number(r.production_required_quantity,locale)}</p>{r.error && <p className="text-red-600">{r.error}</p>}</div>)}</div></div>}
  <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-2 rounded-2xl border border-[var(--brand-border)] bg-[var(--brand-card)] p-3 text-[var(--brand-text)] shadow-lg">{canEdit && <button className={`${button} brand-btn brand-btn-primary`} onClick={()=>save()} disabled={busy}>{busy ? t("checkpointD.actions.loading") : t("checkpointD.actions.saveProject")}</button>}{canEdit && project?.status === "draft" && <button className={`${button} brand-btn brand-btn-secondary`} onClick={()=>save("planned")} disabled={busy || lineInvalid || (!(project?.lines || []).length && !lineDirty)}>{t("checkpointD.actions.plan")}</button>}{project && <button className={`${button} brand-btn brand-btn-secondary`} onClick={doPreview} disabled={busy || hasUnsaved || !(project.lines || []).length}>{t("checkpointD.actions.preview")}</button>}{project?.status === "planned" && hasPermission("production_projects_release") && <button className={`${button} brand-btn brand-btn-primary`} onClick={()=>setConfirm("release")} disabled={releaseDisabled}>{t("checkpointD.actions.release")}</button>}{releaseHint && project?.status === "planned" && <p className="basis-full text-sm font-semibold text-amber-700 dark:text-amber-300">{releaseHint}</p>}</div><ConfirmDialog open={confirm==="release"} title={t("checkpointD.dialogs.releaseTitle")} message={t("checkpointD.dialogs.releaseMessage")} confirmLabel={t("checkpointD.actions.release")} cancelLabel={t("checkpointD.actions.cancel")} onCancel={()=>setConfirm(null)} onConfirm={release}/></section>;
}
