import { useEffect, useMemo, useState } from "react";
import { uploadUrl } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

const TYPES = [
  "PROFILE",
  "SHEET_METAL",
  "STEEL_WIRE",
  "LAMINATE",
  "PLYWOOD",
  "PLASTIC",
  "ACRYLIC",
  "MDF",
  "CHIPBOARD",
  "LAMINATED_CHIPBOARD",
  "PAINT",
  "WELDING_CONSUMABLE",
  "FASTENER",
  "HARDWARE",
  "RUBBER_PVC",
  "PACKAGING",
  "CONSUMABLE",
];
const PROFILES = ["SQUARE", "RECTANGULAR", "ROUND_TUBE", "ANGLE", "U_PROFILE", "C_PROFILE", "Z_PROFILE"];
const UNITS = ["m", "pcs", "dona", "kg", "l", "m2"];
const STEPS = ["general", "technical", "lengths", "warehouse", "additional"];

const value = (raw) => (raw === null || raw === undefined ? "" : String(raw));

function initialForm(material) {
  const type = material?.material_type || "CONSUMABLE";
  return {
    code: material?.code || "",
    name: material?.name || "",
    category_id: material?.category_id ? String(material.category_id) : "",
    material_type: type,
    profile_type: material?.profile_type || "RECTANGULAR",
    unit: material?.unit || (type === "PROFILE" ? "m" : "pcs"),
    purchase_unit: material?.purchase_unit || "pcs",
    minimum_stock: value(material?.minimum_stock ?? 0),
    current_stock: value(material?.current_stock ?? 0),
    unit_cost: value(material?.unit_cost ?? 0),
    steel_grade: material?.steel_grade || "",
    description: material?.description || "",
    width_mm: value(material?.width_mm),
    height_mm: value(material?.height_mm),
    diameter_mm: value(material?.diameter_mm),
    thickness_mm: value(material?.thickness_mm),
    inner_radius_mm: value(material?.inner_radius_mm),
    length_mm: value(material?.length_mm),
    is_active: material?.is_active !== false,
    auto_code: !material && type === "PROFILE",
  };
}

function generatedCode(form) {
  if (form.material_type !== "PROFILE" || !form.thickness_mm) return "";
  const prefix = { SQUARE:"SQ", RECTANGULAR:"RT", ROUND_TUBE:"RD", ANGLE:"AN", U_PROFILE:"UP", C_PROFILE:"CP", Z_PROFILE:"ZP" }[form.profile_type];
  if (!prefix) return "";
  if (form.profile_type === "ROUND_TUBE") return form.diameter_mm ? `PR-${prefix}-${form.diameter_mm}x${form.thickness_mm}`.toUpperCase() : "";
  return form.width_mm && form.height_mm ? `PR-${prefix}-${form.width_mm}x${form.height_mm}x${form.thickness_mm}`.toUpperCase() : "";
}

function dimensions(form) {
  if (form.material_type === "PROFILE") {
    if (form.profile_type === "ROUND_TUBE") {
      return form.diameter_mm && form.thickness_mm
        ? `Ø${form.diameter_mm} × ${form.thickness_mm} mm`
        : "—";
    }

    return form.width_mm && form.height_mm && form.thickness_mm
      ? `${form.width_mm} × ${form.height_mm} × ${form.thickness_mm} mm`
      : "—";
  }

  if ([
    "SHEET_METAL",
    "LAMINATE",
    "PLYWOOD",
    "PLASTIC",
    "ACRYLIC",
    "MDF",
    "CHIPBOARD",
    "LAMINATED_CHIPBOARD",
    "RUBBER_PVC",
  ].includes(form.material_type)) {
    return form.width_mm && form.length_mm && form.thickness_mm
      ? `${form.width_mm} × ${form.length_mm} × ${form.thickness_mm} mm`
      : "—";
  }

  if (form.material_type === "STEEL_WIRE") {
    return form.diameter_mm
      ? `Ø${form.diameter_mm} mm`
      : "—";
  }

  return "—";
}

function positive(raw) { return Number(raw) > 0; }

function technicalMetrics(form) {
  const t = Number(form.thickness_mm), b = Number(form.width_mm), h = Number(form.height_mm), d = Number(form.diameter_mm);
  if (form.material_type === "SHEET_METAL" && b > 0 && Number(form.length_mm) > 0 && t > 0) {
    const area = b * Number(form.length_mm) / 1_000_000;
    return { area, sheetWeight: area * t / 1000 * 7850 };
  }
  if (form.material_type !== "PROFILE" || !(t > 0)) return {};
  let sectionArea = 0;
  if (["SQUARE","RECTANGULAR"].includes(form.profile_type) && b > 2*t && h > 2*t) sectionArea = b*h-(b-2*t)*(h-2*t);
  if (form.profile_type === "ROUND_TUBE" && d > 2*t) sectionArea = Math.PI/4*(d*d-(d-2*t)**2);
  if (form.profile_type === "ANGLE" && b>0 && h>0) sectionArea = t*(b+h-t);
  return sectionArea > 0 ? { weightPerMeter:sectionArea*0.00785 } : {};
}

function ProfileSketch({ form, t }) {
  if (form.material_type !== "PROFILE") return null;
  const round = form.profile_type === "ROUND_TUBE";
  return <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-3">
    <p className="mb-2 text-xs font-bold uppercase tracking-wide text-blue-800">{t("materialMaster.geometryPreview")}</p>
    <svg viewBox="0 0 220 125" className="mx-auto h-32 w-full max-w-[260px]" role="img" aria-label={t("materialMaster.geometryPreview")}>
      {round ? <><circle cx="110" cy="61" r="45" fill="none" stroke="#1d4ed8" strokeWidth="5"/><circle cx="110" cy="61" r="34" fill="none" stroke="#93c5fd" strokeWidth="2"/><line x1="65" y1="112" x2="155" y2="112" stroke="#475569"/><text x="92" y="124" fontSize="11" fill="#334155">D</text></> : <><rect x="50" y="18" width="120" height="78" rx="3" fill="none" stroke="#1d4ed8" strokeWidth="5"/><rect x="62" y="30" width="96" height="54" fill="none" stroke="#93c5fd" strokeWidth="2"/><line x1="50" y1="110" x2="170" y2="110" stroke="#475569"/><text x="106" y="122" fontSize="11" fill="#334155">B</text><line x1="185" y1="18" x2="185" y2="96" stroke="#475569"/><text x="193" y="61" fontSize="11" fill="#334155">H</text></>}
      <text x="22" y="18" fontSize="11" fill="#334155">t = {form.thickness_mm || "—"}</text>
    </svg>
  </div>;
}

export default function MaterialMasterForm({ material, categories, busy, onSubmit, onCancel }) {
  const { t, formatNumber } = useLocale();
  const [form, setForm] = useState(() => initialForm(material));
  const [step, setStep] = useState("general");
  const [lots, setLots] = useState([]);
  const [lotDraft, setLotDraft] = useState({ length_m:"", piece_count:"", warehouse_name:"", location_code:"", lot_number:"", notes:"" });
  const [validation, setValidation] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(material?.image_url || "");

  useEffect(() => {
    if (!imageFile) {
      setImagePreview(material?.image_url || "");
      return undefined;
    }

    const objectUrl = URL.createObjectURL(imageFile);
    setImagePreview(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [imageFile, material?.image_url]);

  const profile = form.material_type === "PROFILE";
  const sheet = form.material_type === "SHEET_METAL";
  const sheetLike = [
  "SHEET_METAL",
  "LAMINATE",
  "PLYWOOD",
  "PLASTIC",
  "ACRYLIC",
  "MDF",
  "CHIPBOARD",
  "LAMINATED_CHIPBOARD",
  "RUBBER_PVC",
].includes(form.material_type);

const wire = form.material_type === "STEEL_WIRE";
  const effectiveCode = form.auto_code ? generatedCode(form) : form.code.trim().toUpperCase();
  const metrics = useMemo(() => technicalMetrics(form), [form]);
  const allLots = [...(material?.length_lots || []), ...lots];
  const lotTotals = useMemo(() => ({
    pieces: allLots.reduce((sum, row) => sum + Number(row.pieces_on_hand ?? row.piece_count ?? 0), 0),
    meters: allLots.reduce((sum, row) => sum + Number(row.total_meters ?? (Number(row.length_m) * Number(row.piece_count) || 0)), 0),
  }), [allLots]);

  const set = (key, next) => setForm((old) => ({ ...old, [key]: next }));
  const setType = (material_type) => setForm((old) => ({
    ...old, material_type,
    unit:
  material_type === "PROFILE" ? "m" :
  material_type === "STEEL_WIRE" ? "m" :
  material_type === "PAINT" ? "kg" :
  ["LAMINATE","PLYWOOD","PLASTIC","ACRYLIC","MDF","CHIPBOARD","LAMINATED_CHIPBOARD","RUBBER_PVC"].includes(material_type) ? "m2" :
  "pcs",

purchase_unit:
  material_type === "PROFILE" ? "pcs" :
  material_type === "STEEL_WIRE" ? "kg" :
  material_type === "PAINT" ? "kg" :
  ["LAMINATE","PLYWOOD","PLASTIC","ACRYLIC","MDF","CHIPBOARD","LAMINATED_CHIPBOARD","RUBBER_PVC"].includes(material_type) ? "pcs" :
  "pcs",
    auto_code: material_type === "PROFILE",
  }));

  const addLot = () => {
    const length = Number(lotDraft.length_m), pieces = Number(lotDraft.piece_count);
    if (!(length > 0) || !(Number.isInteger(pieces) && pieces > 0)) {
      setValidation(t("materialMaster.errors.material_length_lot_invalid")); return;
    }
    setLots((old) => [...old, { ...lotDraft, length_m:length, piece_count:pieces, total_meters:length * pieces }]);
    setLotDraft({ length_m:"", piece_count:"", warehouse_name:"", location_code:"", lot_number:"", notes:"" });
    setValidation("");
  };

  const validate = () => {
    if (!form.category_id) return "material_category_required";
    if (!form.name.trim()) return "material_name_required";
    if (!effectiveCode) return "material_code_required";
    if (Number(form.minimum_stock) < 0 || Number(form.unit_cost) < 0 || (!profile && Number(form.current_stock) < 0)) return "material_quantity_nonnegative";
    if (profile) {
      if (!form.profile_type || !positive(form.thickness_mm)) return "material_dimension_required";
      if (form.profile_type === "ROUND_TUBE" ? !positive(form.diameter_mm) : (!positive(form.width_mm) || !positive(form.height_mm))) return "material_dimension_required";
      if (form.profile_type === "SQUARE" && Number(form.width_mm) !== Number(form.height_mm)) return "profile_square_dimensions";
      if (["SQUARE", "RECTANGULAR"].includes(form.profile_type) && (Number(form.width_mm) <= 2 * Number(form.thickness_mm) || Number(form.height_mm) <= 2 * Number(form.thickness_mm))) return "profile_geometry_invalid";
      if (form.profile_type === "ROUND_TUBE" && Number(form.diameter_mm) <= 2 * Number(form.thickness_mm)) return "profile_geometry_invalid";
    }
    if (sheetLike && (!positive(form.width_mm) || !positive(form.length_mm) || !positive(form.thickness_mm))) return "material_dimension_required";
    if (wire && !positive(form.diameter_mm)) return "material_dimension_required";
    return "";
  };

  const save = () => {
    const issue = validate();
    if (issue) { setValidation(t(`materialMaster.errors.${issue}`)); return; }
    const numberOrNull = (raw) => raw === "" ? null : Number(raw);
    const payload = {
      code: effectiveCode, name: form.name.trim(), category_id: Number(form.category_id),
      material_type: form.material_type, profile_type: profile ? form.profile_type : null,
      unit: form.unit, purchase_unit: form.purchase_unit,
      minimum_stock: Number(form.minimum_stock), unit_cost: Number(form.unit_cost),
      steel_grade: form.steel_grade.trim(), description: form.description.trim(),
      width_mm: (profile || sheetLike) ? numberOrNull(form.width_mm) : null,
      height_mm: profile ? numberOrNull(form.height_mm) : null,
      diameter_mm: (profile || wire) ? numberOrNull(form.diameter_mm) : null,
      thickness_mm: (profile || sheetLike) ? numberOrNull(form.thickness_mm) : null,
      inner_radius_mm: profile ? numberOrNull(form.inner_radius_mm) : null,
      length_mm: sheetLike ? numberOrNull(form.length_mm) : null,
      is_active: form.is_active, auto_code: form.auto_code,
      ...(material ? { new_length_lots: lots } : { current_stock: profile ? 0 : Number(form.current_stock), initial_length_lots: lots }),
    };
    setValidation(""); onSubmit(payload, imageFile);
  };

  const fieldClass = "min-h-[44px] w-full rounded-xl border border-[var(--brand-input-border,var(--brand-border))] bg-[var(--brand-input-background,var(--brand-card))] px-3 text-[var(--brand-input-text,var(--brand-text))] outline-none focus:ring-2 focus:ring-[var(--brand-focus,var(--brand-primary))]";
  const label = (key, child) => <label className="block text-sm"><span className="mb-1 block font-semibold">{t(key)}</span>{child}</label>;
  return <div className="rounded-3xl border bg-[var(--brand-card)] shadow-sm">
    <div className="border-b p-4 sm:p-5"><div className="flex gap-2 overflow-x-auto pb-1" role="tablist">{STEPS.map((name, index) => <button key={name} type="button" onClick={() => setStep(name)} className={`min-h-[42px] shrink-0 rounded-xl px-3 text-sm font-bold ${step===name?"text-white":"border"}`} style={step===name?{backgroundColor:"var(--brand-button)"}:undefined}>{index+1}. {t(`materialMaster.steps.${name}`)}</button>)}</div></div>
    <div className="grid gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-4">
        {step === "general" && <div className="grid gap-4 md:grid-cols-2">
          {label("materialMaster.category", <select className={fieldClass} value={form.category_id} onChange={(e)=>set("category_id",e.target.value)}><option value="">{t("materialMaster.selectCategory")}</option>{categories.map((row)=><option key={row.id} value={row.id}>{row.name}</option>)}</select>)}
          {label("materialMaster.materialType", <select className={fieldClass} value={form.material_type} onChange={(e)=>setType(e.target.value)}>{TYPES.map((name)=><option key={name} value={name}>{t(`materialMaster.types.${name}`)}</option>)}</select>)}
          {label("materialMaster.code", <div className="flex gap-2"><input className={`${fieldClass} font-mono`} value={form.auto_code?effectiveCode:form.code} readOnly={form.auto_code} onChange={(e)=>set("code",e.target.value.toUpperCase())}/>{profile&&<label className="flex shrink-0 items-center gap-2 rounded-xl border px-3 text-xs font-bold"><input type="checkbox" checked={form.auto_code} onChange={(e)=>set("auto_code",e.target.checked)}/>{t("materialMaster.auto")}</label>}</div>)}
          {label("materialMaster.name", <input className={fieldClass} value={form.name} onChange={(e)=>set("name",e.target.value)}/>)}
        </div>}
        {step === "technical" && <div className="grid gap-4 md:grid-cols-2">
          {profile&&label("materialMaster.profileType",<select className={fieldClass} value={form.profile_type} onChange={(e)=>set("profile_type",e.target.value)}>{PROFILES.map((name)=><option key={name} value={name}>{t(`materialMaster.profiles.${name}`)}</option>)}</select>)}
          {(profile||sheetLike)&&form.profile_type!=="ROUND_TUBE"&&label("materialMaster.widthMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.width_mm} onChange={(e)=>set("width_mm",e.target.value)}/>)}
          {profile&&form.profile_type!=="ROUND_TUBE"&&label("materialMaster.heightMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.height_mm} onChange={(e)=>set("height_mm",e.target.value)}/>)}
          {profile&&form.profile_type==="ROUND_TUBE"&&label("materialMaster.diameterMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.diameter_mm} onChange={(e)=>set("diameter_mm",e.target.value)}/>)}
          {sheetLike&&label("materialMaster.lengthMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.length_mm} onChange={(e)=>set("length_mm",e.target.value)}/>)}
         {(profile||sheetLike)&&label("materialMaster.thicknessMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.thickness_mm} onChange={(e)=>set("thickness_mm",e.target.value)}/>)}
          {profile&&["ANGLE","U_PROFILE","C_PROFILE","Z_PROFILE"].includes(form.profile_type)&&label("materialMaster.innerRadiusMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.inner_radius_mm} onChange={(e)=>set("inner_radius_mm",e.target.value)}/>)}
         {wire&&label("materialMaster.diameterMm",<input type="number" min="0.001" step="any" className={fieldClass} value={form.diameter_mm} onChange={(e)=>set("diameter_mm",e.target.value)}/>)}
          {!profile&&!sheetLike&&!wire&&<p className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900 md:col-span-2">{t("materialMaster.noTechnicalFields")}</p>}
        </div>}
        {step === "lengths" && <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">{label("materialMaster.baseUnit",<select className={fieldClass} value={form.unit} onChange={(e)=>set("unit",e.target.value)}>{UNITS.map((u)=><option key={u} value={u}>{t(`materialMaster.units.${u}`)}</option>)}</select>)}{label("materialMaster.purchaseUnit",<select className={fieldClass} value={form.purchase_unit} onChange={(e)=>set("purchase_unit",e.target.value)}>{UNITS.map((u)=><option key={u} value={u}>{t(`materialMaster.units.${u}`)}</option>)}</select>)}</div>
          {profile?<><div className="grid gap-2 rounded-2xl border border-blue-100 bg-blue-50/50 p-3 sm:grid-cols-2 lg:grid-cols-3">{[["length_m","lengthM"],["piece_count","pieces"],["warehouse_name","warehouse"],["location_code","location"],["lot_number","lotNumber"],["notes","notes"]].map(([key,k])=><input key={key} type={["length_m","piece_count"].includes(key)?"number":"text"} min="0" step={key==="piece_count"?"1":"any"} className={fieldClass} value={lotDraft[key]} onChange={(e)=>setLotDraft({...lotDraft,[key]:e.target.value})} placeholder={t(`materialMaster.${k}`)}/>)}<button type="button" onClick={addLot} className="min-h-[44px] rounded-xl bg-blue-700 px-4 font-bold text-white sm:col-span-2 lg:col-span-3">+ {t("materialMaster.addLot")}</button></div>
          <div className="overflow-x-auto rounded-2xl border"><table className="w-full min-w-[720px] text-sm"><thead className="bg-slate-900 text-white"><tr>{["lengthM","pieces","totalMeters","warehouse","location","lotNumber","action"].map((k)=><th key={k} className="px-3 py-2 text-left">{t(`materialMaster.${k}`)}</th>)}</tr></thead><tbody>{allLots.map((row,index)=><tr key={row.id||`new-${index}`} className="border-t"><td className="px-3 py-2">{row.length_m}</td><td className="px-3 py-2">{row.pieces_on_hand??row.piece_count}</td><td className="px-3 py-2 font-bold">{row.total_meters??Number(row.length_m)*Number(row.piece_count)}</td><td className="px-3 py-2">{row.warehouse_name||"—"}</td><td className="px-3 py-2">{row.location_code||"—"}</td><td className="px-3 py-2">{row.lot_number||"—"}</td><td className="px-3 py-2">{row.id?<span className="text-xs text-slate-500">{t("materialMaster.persisted")}</span>:<button type="button" className="font-bold text-red-700" onClick={()=>setLots((current)=>current.filter((_,newIndex)=>newIndex!==index-(material?.length_lots?.length||0)))}>{t("common.delete")}</button>}</td></tr>)}</tbody><tfoot><tr className="border-t bg-slate-50 font-black"><td className="px-3 py-2">{t("materialMaster.total")}</td><td className="px-3 py-2">{lotTotals.pieces}</td><td className="px-3 py-2">{formatNumber(lotTotals.meters)} m</td><td colSpan="4"/></tr></tfoot></table></div></>:<p className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">{sheet?t("materialMaster.sheetUnitHelp"):t("materialMaster.standardUnitHelp")}</p>}
        </div>}
        {step === "warehouse" && <div className="grid gap-4 sm:grid-cols-2">{label("materialMaster.minimumStock",<input type="number" min="0" step="any" className={fieldClass} value={form.minimum_stock} onChange={(e)=>set("minimum_stock",e.target.value)}/>)}{label("materialMaster.unitCost",<input type="number" min="0" step="any" className={fieldClass} value={form.unit_cost} onChange={(e)=>set("unit_cost",e.target.value)}/>)}{!material&&!profile&&label(sheet?"materialMaster.sheetCount":"materialMaster.openingStock",<input type="number" min="0" step="any" className={fieldClass} value={form.current_stock} onChange={(e)=>set("current_stock",e.target.value)}/>)}<label className="flex min-h-[48px] items-center gap-3 rounded-xl border px-3 text-sm font-bold"><input type="checkbox" checked={form.is_active} onChange={(e)=>set("is_active",e.target.checked)}/>{form.is_active?t("materialMaster.active"):t("materialMaster.inactive")}</label></div>}
        {step === "additional" && <div className="space-y-4">{(profile||sheet)&&label("materialMaster.steelGrade",<input className={fieldClass} value={form.steel_grade} onChange={(e)=>set("steel_grade",e.target.value)}/>)}{label("materialMaster.notes",<textarea rows="5" className={`${fieldClass} py-3`} value={form.description} onChange={(e)=>set("description",e.target.value)}/>)}</div>}
        {validation&&<p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-800">{validation}</p>}
      </div>
      <aside className="space-y-3 rounded-2xl border border-blue-100 bg-gradient-to-b from-blue-50 to-white p-4 text-slate-900 xl:sticky xl:top-4 xl:self-start">
        <div className="overflow-hidden rounded-2xl border bg-white">
          {imagePreview ? (
            <img
              src={
                imagePreview.startsWith("blob:") ||
                imagePreview.startsWith("data:") ||
                imagePreview.startsWith("http")
                  ? imagePreview
                  : uploadUrl(imagePreview)
              }
              alt={form.name || effectiveCode || "Material"}
              className="h-52 w-full object-contain"
            />
          ) : (
            <div className="flex h-52 items-center justify-center px-4 text-center text-sm font-semibold text-slate-400">
              Material rasmi
            </div>
          )}
        </div>

        <label className="block rounded-xl border bg-white p-3 text-sm">
          <span className="mb-2 block font-bold text-slate-700">Material rasmi</span>
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif"
            className="block w-full text-sm"
            onChange={(e) => setImageFile(e.target.files?.[0] || null)}
          />
          <span className="mt-1 block text-xs text-slate-500">PNG, JPG, WEBP yoki GIF · maksimum 5 MB</span>
        </label>

        <p className="text-xs font-black uppercase tracking-[0.16em] text-blue-700">{t("materialMaster.card")}</p>
        <p className="break-all font-mono text-lg font-black text-blue-950">{effectiveCode||"—"}</p>
        <p className="text-lg font-bold">{form.name||t("materialMaster.unnamed")}</p>
        <p className="text-sm text-slate-600">{t(`materialMaster.types.${form.material_type}`)}{form.steel_grade?` / ${form.steel_grade}`:""}</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-sm"><dt className="text-slate-500">{t("materialMaster.size")}</dt><dd className="font-bold">{dimensions(form)}</dd><dt className="text-slate-500">{t("materialMaster.lengths")}</dt><dd className="font-bold">{lotTotals.meters?allLots.map((x)=>x.length_m).filter((x,i,a)=>a.indexOf(x)===i).join(" / ")+" m":"—"}</dd>{profile&&<><dt className="text-slate-500">{t("materialMaster.total")}</dt><dd className="font-bold">{lotTotals.pieces} {t("materialMaster.units.pcs")} / {formatNumber(lotTotals.meters)} m</dd></>}<dt className="text-slate-500">{t("materialMaster.baseUnit")}</dt><dd className="font-bold">{t(`materialMaster.units.${form.unit}`)}</dd><dt className="text-slate-500">{t("materialMaster.purchaseUnit")}</dt><dd className="font-bold">{t(`materialMaster.units.${form.purchase_unit}`)}</dd>{metrics.weightPerMeter&&<><dt className="text-slate-500">{t("materialMaster.theoreticalWeight")}</dt><dd className="font-bold">{formatNumber(metrics.weightPerMeter,{maximumFractionDigits:3})} kg/m</dd></>}{metrics.area&&<><dt className="text-slate-500">{t("materialMaster.sheetArea")}</dt><dd className="font-bold">{formatNumber(metrics.area,{maximumFractionDigits:3})} m²</dd><dt className="text-slate-500">{t("materialMaster.sheetWeight")}</dt><dd className="font-bold">{formatNumber(metrics.sheetWeight,{maximumFractionDigits:3})} kg</dd></>}</dl><ProfileSketch form={form} t={t}/>
      </aside>
    </div>
    <div className="flex flex-col-reverse gap-2 border-t p-4 sm:flex-row sm:justify-end"><button type="button" disabled={busy} onClick={onCancel} className="min-h-[48px] rounded-xl border px-6 font-bold">{t("common.cancel")}</button><button type="button" disabled={busy} onClick={save} className="min-h-[48px] rounded-xl px-8 font-black text-white disabled:opacity-60" style={{backgroundColor:"var(--brand-button)"}}>{busy?t("common.saving"):t("common.save")}</button></div>
  </div>;
}
