import { useCallback, useEffect, useRef, useState } from "react";
import { api, getApiBase } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

function resolveUploadUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${getApiBase()}${url}`;
}

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export default function MesBomEditor({ templateId, readOnly = false, onSummaryChange }) {
  const { t } = useLocale();
  const [lines, setLines] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState("grid");
  const [partSearch, setPartSearch] = useState("");
  const [debouncedPartSearch, setDebouncedPartSearch] = useState("");
  const [parts, setParts] = useState([]);
  const [partsLoading, setPartsLoading] = useState(false);
  const [selectedPartId, setSelectedPartId] = useState("");
  const [addQty, setAddQty] = useState("1");
  const [savingId, setSavingId] = useState(null);
  const [yigishLines, setYigishLines] = useState([]);
  const [yigishSummary, setYigishSummary] = useState(null);
  const [yigishLoading, setYigishLoading] = useState(true);
  const [yigishMaterialSearch, setYigishMaterialSearch] = useState("");
  const [yigishDebouncedMaterialSearch, setYigishDebouncedMaterialSearch] = useState("");
  const [yigishMaterials, setYigishMaterials] = useState([]);
  const [yigishMaterialsLoading, setYigishMaterialsLoading] = useState(false);
  const [selectedYigishMaterialId, setSelectedYigishMaterialId] = useState("");
  const [yigishAddQty, setYigishAddQty] = useState("1");
  const [yigishSavingId, setYigishSavingId] = useState(null);
  const drawingRefs = useRef({});

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedPartSearch(partSearch), 300);
    return () => window.clearTimeout(timer);
  }, [partSearch]);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setYigishDebouncedMaterialSearch(yigishMaterialSearch),
      300
    );
    return () => window.clearTimeout(timer);
  }, [yigishMaterialSearch]);

  const onSummaryChangeRef = useRef(onSummaryChange);
  useEffect(() => {
    onSummaryChangeRef.current = onSummaryChange;
  }, [onSummaryChange]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const data = await api.mesGetTemplateBom(templateId);
        if (cancelled) return;
        setLines(data.lines || []);
        setSummary(data.summary || null);
        onSummaryChangeRef.current?.(data.summary || null);
      } catch (e) {
        if (cancelled) return;
        setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [templateId]);

  const loadBom = useCallback(async () => {
    setError("");
    try {
      const data = await api.mesGetTemplateBom(templateId);
      setLines(data.lines || []);
      setSummary(data.summary || null);
      onSummaryChangeRef.current?.(data.summary || null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  const loadYigish = useCallback(async () => {
    setYigishLoading(true);
    try {
      const data = await api.mesGetTemplateYigish(templateId);
      setYigishLines(data.lines || []);
      setYigishSummary(data.summary || null);
    } catch (e) {
      setYigishLines([]);
      setYigishSummary(null);
      setError(e.message);
    } finally {
      setYigishLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    if (readOnly) return;
    let cancelled = false;
    const loadParts = async () => {
      setPartsLoading(true);
      try {
        const data = await api.mesGetParts({ q: debouncedPartSearch });
        if (!cancelled) setParts(data.parts || []);
      } catch {
        if (!cancelled) setParts([]);
      } finally {
        if (!cancelled) setPartsLoading(false);
      }
    };
    loadParts();
    return () => {
      cancelled = true;
    };
  }, [debouncedPartSearch, readOnly]);

  useEffect(() => {
    let cancelled = false;

    const loadYigishMaterials = async () => {
      if (readOnly) return;

      setYigishMaterialsLoading(true);
      try {
        const data = await api.materialsItems();
        if (!cancelled) {
          const query = String(yigishDebouncedMaterialSearch || "").trim().toLowerCase();
          const materials = (data.materials || [])
            .filter((item) => item.is_active !== false)
            .filter((item) => {
              if (!query) return true;
              return JSON.stringify(item).toLowerCase().includes(query);
            });
          setYigishMaterials(materials);
        }
      } catch {
        if (!cancelled) setYigishMaterials([]);
      } finally {
        if (!cancelled) setYigishMaterialsLoading(false);
      }
    };

    loadYigishMaterials();

    return () => {
      cancelled = true;
    };
  }, [yigishDebouncedMaterialSearch, readOnly]);

  useEffect(() => {
    loadYigish();
  }, [loadYigish]);

  const existingPartIds = new Set(lines.map((l) => l.part_id));
  const existingYigishMaterialIds = new Set(
    yigishLines.filter((l) => l.material_id).map((l) => l.material_id)
  );

  const addLine = async () => {
    const partId = Number(selectedPartId);
    const qty = Number(addQty);
    if (!partId || !qty || qty <= 0) return;
    try {
      await api.mesAddBomLine(templateId, {
        part_id: partId,
        required_quantity: qty,
      });
      setSelectedPartId("");
      setAddQty("1");
      setPartSearch("");
      await loadBom();
    } catch (e) {
      setError(e.message);
    }
  };

  const addYigishLine = async () => {
    const materialId = Number(selectedYigishMaterialId);
    const qty = Number(yigishAddQty);

    if (!materialId || !qty || qty <= 0) return;

    try {
      await api.mesAddYigishLine(templateId, {
        material_id: materialId,
        required_quantity: qty,
      });

      setSelectedYigishMaterialId("");
      setYigishAddQty("1");
      setYigishMaterialSearch("");
      await loadYigish();
    } catch (e) {
      setError(e.message);
    }
  };

  const removeYigishLine = async (line) => {
    if (!window.confirm(`${line.part_number} — ${t("mes.confirmDelete")}?`)) return;

    try {
      await api.mesDeleteYigishLine(templateId, line.id);
      await loadYigish();
    } catch (e) {
      setError(e.message);
    }
  };

  const updateYigishLine = async (line, patch) => {
    setYigishSavingId(line.id);

    try {
      await api.mesUpdateYigishLine(templateId, line.id, patch);
      await loadYigish();
    } catch (e) {
      setError(e.message);
    } finally {
      setYigishSavingId(null);
    }
  };

  const moveYigishLine = async (index, direction) => {
    const target = index + direction;

    if (target < 0 || target >= yigishLines.length) return;

    const reordered = [...yigishLines];
    const [item] = reordered.splice(index, 1);
    reordered.splice(target, 0, item);

    const payload = reordered.map((line, idx) => ({
      id: line.id,
      sort_order: idx,
    }));

    try {
      const data = await api.mesReorderYigishLines(templateId, payload);
      setYigishLines(data.lines || []);
      setYigishSummary(data.summary || null);
    } catch (e) {
      setError(e.message);
    }
  };

  const removeLine = async (line) => {
    if (!window.confirm(`${line.part_number} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeleteBomLine(templateId, line.id);
      await loadBom();
    } catch (e) {
      setError(e.message);
    }
  };

  const updateLine = async (line, patch) => {
    setSavingId(line.id);
    try {
      await api.mesUpdateBomLine(templateId, line.id, patch);
      await loadBom();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingId(null);
    }
  };

  const moveLine = async (index, direction) => {
    const target = index + direction;
    if (target < 0 || target >= lines.length) return;
    const reordered = [...lines];
    const [item] = reordered.splice(index, 1);
    reordered.splice(target, 0, item);
    const payload = reordered.map((line, idx) => ({ id: line.id, sort_order: idx }));
    try {
      const data = await api.mesReorderBomLines(templateId, payload);
      setLines(data.lines || []);
      setSummary(data.summary || null);
      onSummaryChange?.(data.summary || null);
    } catch (e) {
      setError(e.message);
    }
  };

  const uploadDrawing = async (line, file) => {
    if (!file) return;
    setSavingId(line.id);
    try {
      await api.mesUploadBomDrawing(templateId, line.id, file);
      await loadBom();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingId(null);
    }
  };

  if (loading) {
    return <p className="py-6 text-center text-sm text-[var(--brand-muted)]">{t("common.loading")}</p>;
  }

  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-bold">{t("mes.bomEditor")}</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${
              viewMode === "grid" ? "bg-gray-100" : ""
            }`}
          >
            {t("mes.bomGridView")}
          </button>
          <button
            type="button"
            onClick={() => setViewMode("tree")}
            className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${
              viewMode === "tree" ? "bg-gray-100" : ""
            }`}
          >
            {t("mes.bomTreeView")}
          </button>
        </div>
      </div>

      {readOnly && (
        <p className="mb-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("mes.bomReadOnly")}
        </p>
      )}

      {!readOnly && (
        <div className="mb-6 rounded-xl border bg-gray-50 p-4">
          <p className="mb-2 text-sm font-semibold">{t("mes.addBomPart")}</p>
          <input
            value={partSearch}
            onChange={(e) => setPartSearch(e.target.value)}
            placeholder={t("mes.searchParts")}
            className="mb-2 w-full rounded-xl border px-4 py-2 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <select
              value={selectedPartId}
              onChange={(e) => setSelectedPartId(e.target.value)}
              className="min-w-[200px] flex-1 rounded-xl border px-3 py-2 text-sm"
            >
              <option value="">{partsLoading ? t("common.loading") : t("mes.selectPart")}</option>
              {parts
                .filter((p) => !existingPartIds.has(p.id))
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.part_number} — {p.name}
                  </option>
                ))}
            </select>
            <input
              type="number"
              min="0.01"
              step="any"
              value={addQty}
              onChange={(e) => setAddQty(e.target.value)}
              className="w-24 rounded-xl border px-3 py-2 text-sm"
              title={t("mes.requiredQty")}
            />
            <button
              type="button"
              onClick={addLine}
              disabled={!selectedPartId || Number(addQty) <= 0}
              className="rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              {t("mes.addPart")}
            </button>
          </div>
        </div>
      )}

      {lines.length === 0 ? (
        <p className="py-8 text-center text-[var(--brand-muted)]">{t("mes.emptyBom")}</p>
      ) : viewMode === "grid" ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b text-[var(--brand-muted)]">
                <th className="px-2 py-2">#</th>
                <th className="px-2 py-2">{t("mes.partNumber")}</th>
                <th className="px-2 py-2">{t("mes.name")}</th>
                <th className="px-2 py-2">{t("mes.requiredQty")}</th>
                <th className="px-2 py-2">{t("mes.producedQty")}</th>
                <th className="px-2 py-2">{t("mes.acceptedQty")}</th>
                <th className="px-2 py-2">{t("mes.rejectedQty")}</th>
                <th className="px-2 py-2">{t("mes.notes")}</th>
                <th className="px-2 py-2">{t("mes.drawing")}</th>
                {!readOnly && <th className="px-2 py-2" />}
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={line.id} className="border-b align-top">
                  <td className="px-2 py-2 font-mono text-xs">{index + 1}</td>
                  <td className="px-2 py-2 font-mono font-semibold">
                    {line.material_code || line.part_number || `MAT-${line.material_id || ""}`}
                    {(line.part_deleted || !line.part_is_active) && (
                      <span className="ml-1 rounded bg-red-100 px-1 text-xs text-red-700">
                        {t("mes.partInactive")}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-2">{line.part_name}</td>
                  <td className="px-2 py-2">
                    {readOnly ? (
                      formatQty(line.required_quantity)
                    ) : (
                      <input
                        type="number"
                        min="0.01"
                        step="any"
                        defaultValue={line.required_quantity}
                        disabled={savingId === line.id}
                        onBlur={(e) => {
                          const val = Number(e.target.value);
                          if (val > 0 && val !== line.required_quantity) {
                            updateLine(line, { required_quantity: val });
                          } else if (val <= 0) {
                            e.target.value = line.required_quantity;
                          }
                        }}
                        className="w-20 rounded border px-2 py-1"
                      />
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {readOnly ? (
                      formatQty(line.produced_quantity)
                    ) : (
                      <input
                        type="number"
                        min="0"
                        step="any"
                        defaultValue={line.produced_quantity}
                        disabled={savingId === line.id}
                        onBlur={(e) => {
                          const val = Number(e.target.value);
                          if (!Number.isNaN(val) && val !== line.produced_quantity) {
                            updateLine(line, { produced_quantity: val });
                          }
                        }}
                        className="w-20 rounded border px-2 py-1"
                      />
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {readOnly ? (
                      formatQty(line.accepted_quantity)
                    ) : (
                      <input
                        type="number"
                        min="0"
                        step="any"
                        defaultValue={line.accepted_quantity}
                        disabled={savingId === line.id}
                        onBlur={(e) => {
                          const val = Number(e.target.value);
                          if (!Number.isNaN(val) && val !== line.accepted_quantity) {
                            updateLine(line, { accepted_quantity: val });
                          }
                        }}
                        className="w-20 rounded border px-2 py-1"
                      />
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {readOnly ? (
                      formatQty(line.rejected_quantity)
                    ) : (
                      <input
                        type="number"
                        min="0"
                        step="any"
                        defaultValue={line.rejected_quantity}
                        disabled={savingId === line.id}
                        onBlur={(e) => {
                          const val = Number(e.target.value);
                          if (!Number.isNaN(val) && val !== line.rejected_quantity) {
                            updateLine(line, { rejected_quantity: val });
                          }
                        }}
                        className="w-20 rounded border px-2 py-1"
                      />
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {readOnly ? (
                      line.notes || "—"
                    ) : (
                      <input
                        type="text"
                        defaultValue={line.notes}
                        disabled={savingId === line.id}
                        onBlur={(e) => {
                          if (e.target.value !== (line.notes || "")) {
                            updateLine(line, { notes: e.target.value });
                          }
                        }}
                        className="min-w-[120px] rounded border px-2 py-1"
                      />
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {line.drawing_url ? (
                      <a
                        href={resolveUploadUrl(line.drawing_url)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--brand-primary)] hover:underline"
                      >
                        {t("mes.viewDrawing")}
                      </a>
                    ) : (
                      "—"
                    )}
                    {!readOnly && (
                      <>
                        <input
                          ref={(el) => {
                            drawingRefs.current[line.id] = el;
                          }}
                          type="file"
                          accept="image/*,.pdf"
                          className="hidden"
                          onChange={(e) => uploadDrawing(line, e.target.files?.[0])}
                        />
                        <button
                          type="button"
                          onClick={() => drawingRefs.current[line.id]?.click()}
                          className="ml-2 text-xs text-[var(--brand-primary)]"
                        >
                          {t("mes.uploadDrawing")}
                        </button>
                      </>
                    )}
                  </td>
                  {!readOnly && (
                    <td className="px-2 py-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => moveLine(index, -1)}
                        disabled={index === 0}
                        className="rounded border px-2 py-0.5 text-xs disabled:opacity-30"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => moveLine(index, 1)}
                        disabled={index === lines.length - 1}
                        className="ml-1 rounded border px-2 py-0.5 text-xs disabled:opacity-30"
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        onClick={() => removeLine(line)}
                        className="ml-2 text-xs text-red-600"
                      >
                        {t("mes.delete")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ul className="space-y-3">
          {lines.map((line, index) => (
            <li key={line.id} className="relative rounded-xl border p-4 pl-8">
              <span className="absolute left-3 top-4 font-mono text-xs text-[var(--brand-muted)]">
                {index + 1}
              </span>
              {index < lines.length - 1 && (
                <span className="absolute bottom-0 left-4 top-8 w-px bg-gray-200" aria-hidden />
              )}
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-mono font-bold">
                    {line.part_number}
                    {(line.part_deleted || !line.part_is_active) && (
                      <span className="ml-2 rounded bg-red-100 px-1 text-xs text-red-700">
                        {t("mes.partInactive")}
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-[var(--brand-muted)]">{line.part_name}</p>
                  {line.notes && (
                    <p className="mt-1 text-sm italic text-[var(--brand-muted)]">{line.notes}</p>
                  )}
                </div>
                {!readOnly && (
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => moveLine(index, -1)}
                      disabled={index === 0}
                      className="rounded border px-2 py-0.5 text-xs disabled:opacity-30"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => moveLine(index, 1)}
                      disabled={index === lines.length - 1}
                      className="rounded border px-2 py-0.5 text-xs disabled:opacity-30"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      onClick={() => removeLine(line)}
                      className="rounded border border-red-200 px-2 py-0.5 text-xs text-red-600"
                    >
                      {t("mes.delete")}
                    </button>
                  </div>
                )}
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-[var(--brand-muted)]">{t("mes.requiredQty")}</dt>
                  <dd className="font-semibold">{formatQty(line.required_quantity)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--brand-muted)]">{t("mes.producedQty")}</dt>
                  <dd>{formatQty(line.produced_quantity)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--brand-muted)]">{t("mes.acceptedQty")}</dt>
                  <dd>{formatQty(line.accepted_quantity)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--brand-muted)]">{t("mes.rejectedQty")}</dt>
                  <dd>{formatQty(line.rejected_quantity)}</dd>
                </div>
              </dl>
              {line.drawing_url && (
                <a
                  href={resolveUploadUrl(line.drawing_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-sm text-[var(--brand-primary)] hover:underline"
                >
                  {t("mes.viewDrawing")}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {summary && (
        <div className="mt-4 grid grid-cols-2 gap-2 border-t pt-4 text-sm sm:grid-cols-5">
          <div>
            <span className="text-[var(--brand-muted)]">{t("mes.bomPartsCount")}: </span>
            <strong>{summary.parts_count}</strong>
          </div>
          <div>
            <span className="text-[var(--brand-muted)]">{t("mes.totalRequired")}: </span>
            <strong>{formatQty(summary.total_required_quantity)}</strong>
          </div>
          <div>
            <span className="text-[var(--brand-muted)]">{t("mes.totalProduced")}: </span>
            <strong>{formatQty(summary.total_produced_quantity)}</strong>
          </div>
          <div>
            <span className="text-[var(--brand-muted)]">{t("mes.totalAccepted")}: </span>
            <strong>{formatQty(summary.total_accepted_quantity)}</strong>
          </div>
          <div>
            <span className="text-[var(--brand-muted)]">{t("mes.totalRejected")}: </span>
            <strong>{formatQty(summary.total_rejected_quantity)}</strong>
          </div>
        </div>
      )}

      {/* =========================================================
          YIG'ISH DETALLARI
          Faqat shablonda alohida Yig'ish bo'limiga qo'shilgan
          detallar shu yerda ko'rsatiladi.
      ========================================================== */}
      <section className="mt-6 overflow-hidden rounded-2xl border border-sky-200 bg-gradient-to-br from-sky-50/80 via-white to-slate-50">
        <div className="border-b border-sky-100 px-4 py-4 sm:px-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-xl">
                🔧
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">
                  Yig‘ish materiallari
                </h4>
                <p className="mt-0.5 text-xs text-slate-500">
                  Tayyor mahsulotni yig‘ishda alohida kerak bo‘ladigan materiallar
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-bold text-sky-700">
                {yigishSummary?.parts_count ?? yigishLines.length} ta material
              </span>
              {yigishSummary && (
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
                  Jami: {formatQty(yigishSummary.total_required_quantity)}
                </span>
              )}
            </div>
          </div>
        </div>

        {!readOnly && (
          <div className="border-b border-sky-100 bg-white/70 px-4 py-4 sm:px-5">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-800">
                + Yig‘ish materialini qo‘shish
              </p>
              <span className="text-[11px] text-slate-400">
                Material kodi yoki nomi orqali kerakli materialni tanlang
              </span>
            </div>

            <input
              value={yigishMaterialSearch}
              onChange={(e) => setYigishMaterialSearch(e.target.value)}
              placeholder="Material kodi yoki nomini qidiring..."
              className="mb-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />

            <div className="flex flex-col gap-2 sm:flex-row">
              <select
                value={selectedYigishMaterialId}
                onChange={(e) => setSelectedYigishMaterialId(e.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-sky-400"
              >
                <option value="">
                  {yigishMaterialsLoading
                    ? t("common.loading")
                    : "Yig‘ish materiali tanlang"}
                </option>

                {yigishMaterials
                  .filter((material) => !existingYigishMaterialIds.has(material.id))
                  .map((material) => (
                    <option key={material.id} value={material.id}>
                      {material.code || `MAT-${material.id}`} — {material.name}
                      {material.unit ? ` (${material.unit})` : ""}
                    </option>
                  ))}
              </select>

              <input
                type="number"
                min="0.01"
                step="any"
                value={yigishAddQty}
                onChange={(e) => setYigishAddQty(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm sm:w-28"
                placeholder="Miqdor"
                title="Yig‘ish uchun kerakli miqdor"
              />

              <button
                type="button"
                onClick={addYigishLine}
                disabled={!selectedYigishMaterialId || Number(yigishAddQty) <= 0}
                className="rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                + Qo‘shish
              </button>
            </div>
          </div>
        )}

        <div className="p-4 sm:p-5">
          {yigishLoading ? (
            <div className="flex items-center justify-center py-8 text-sm text-slate-500">
              Yig‘ish materiallari yuklanmoqda...
            </div>
          ) : yigishLines.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-8 text-center">
              <div className="mb-2 text-3xl">🔩</div>
              <p className="text-sm font-semibold text-slate-700">
                Yig‘ish uchun qo‘shimcha detal kiritilmagan
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Bu shablon uchun alohida yig‘ish detali talab qilinmaydi.
              </p>
            </div>
          ) : (
            <>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Yig‘ish tarkibi
                </p>
                <span className="text-xs text-slate-500">
                  {yigishLines.length} ta pozitsiya
                </span>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="w-full min-w-[700px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-3 font-semibold">#</th>
                      <th className="px-3 py-3 font-semibold">Material kodi</th>
                      <th className="px-3 py-3 font-semibold">Material nomi</th>
                      <th className="px-3 py-3 font-semibold">Miqdor</th>
                      <th className="px-3 py-3 font-semibold">Birlik</th>
                      <th className="px-3 py-3 font-semibold">Izoh</th>
                      {!readOnly && (
                        <th className="px-3 py-3 text-right font-semibold">
                          Amallar
                        </th>
                      )}
                    </tr>
                  </thead>

                  <tbody>
                    {yigishLines.map((line, index) => (
                      <tr
                        key={line.id}
                        className="border-t border-slate-100 align-middle hover:bg-sky-50/40"
                      >
                        <td className="px-3 py-3">
                          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-500">
                            {index + 1}
                          </span>
                        </td>

                        <td className="px-3 py-3">
                          <span className="font-mono font-bold text-slate-800">
                            {line.material_code || line.part_number || `MAT-${line.material_id || ""}`}
                          </span>
                        </td>

                        <td className="px-3 py-3 font-medium text-slate-700">
                          {line.material_name || line.part_name}
                        </td>

                        <td className="px-3 py-3">
                          {readOnly ? (
                            <span className="font-bold">
                              {formatQty(line.required_quantity)}
                            </span>
                          ) : (
                            <input
                              type="number"
                              min="0.01"
                              step="any"
                              defaultValue={line.required_quantity}
                              disabled={yigishSavingId === line.id}
                              onBlur={(e) => {
                                const value = Number(e.target.value);

                                if (
                                  value > 0 &&
                                  value !== line.required_quantity
                                ) {
                                  updateYigishLine(line, {
                                    required_quantity: value,
                                  });
                                } else if (value <= 0) {
                                  e.target.value = line.required_quantity;
                                }
                              }}
                              className="w-24 rounded-lg border border-slate-200 px-2.5 py-1.5 font-semibold"
                            />
                          )}
                        </td>

                        <td className="px-3 py-3 text-slate-500">
                          {line.unit || "dona"}
                        </td>

                        <td className="px-3 py-3">
                          {readOnly ? (
                            line.notes || "—"
                          ) : (
                            <input
                              type="text"
                              defaultValue={line.notes || ""}
                              disabled={yigishSavingId === line.id}
                              onBlur={(e) => {
                                const value = e.target.value;
                                if (value !== (line.notes || "")) {
                                  updateYigishLine(line, { notes: value });
                                }
                              }}
                              placeholder="Izoh..."
                              className="min-w-[140px] rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm"
                            />
                          )}
                        </td>

                        {!readOnly && (
                          <td className="px-3 py-3">
                            <div className="flex justify-end gap-1.5">
                              <button
                                type="button"
                                onClick={() => moveYigishLine(index, -1)}
                                disabled={index === 0}
                                className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-bold hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
                                title="Yuqoriga"
                              >
                                ↑
                              </button>

                              <button
                                type="button"
                                onClick={() => moveYigishLine(index, 1)}
                                disabled={index === yigishLines.length - 1}
                                className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-bold hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
                                title="Pastga"
                              >
                                ↓
                              </button>

                              <button
                                type="button"
                                onClick={() => removeYigishLine(line)}
                                disabled={yigishSavingId === line.id}
                                className="rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-40"
                              >
                                O‘chirish
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {yigishSummary && (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-white p-3 ring-1 ring-slate-200">
                    <p className="text-xs text-slate-400">Pozitsiyalar</p>
                    <p className="mt-1 text-lg font-bold text-slate-800">
                      {yigishSummary.parts_count}
                    </p>
                  </div>

                  <div className="rounded-xl bg-white p-3 ring-1 ring-slate-200">
                    <p className="text-xs text-slate-400">Jami miqdor</p>
                    <p className="mt-1 text-lg font-bold text-slate-800">
                      {formatQty(yigishSummary.total_required_quantity)}
                    </p>
                  </div>

                  <div className="rounded-xl bg-white p-3 ring-1 ring-slate-200">
                    <p className="text-xs text-slate-400">Holat</p>
                    <p className="mt-1 text-sm font-bold text-emerald-600">
                      Yig‘ish tarkibi tayyor
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  );
}
