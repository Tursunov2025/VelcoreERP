import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";
import MesRouteTimeline from "./MesRouteTimeline";

const emptyStageForm = { name: "", department: "Admin" };

export default function MesRouteDesigner({ templateId, readOnly = false, onRouteChange }) {
  const { t } = useLocale();
  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [stages, setStages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dragIndex, setDragIndex] = useState(null);
  const [newRouteName, setNewRouteName] = useState("");
  const [addStageId, setAddStageId] = useState("");
  const [addMinutes, setAddMinutes] = useState("");
  const [addDepartment, setAddDepartment] = useState("");
  const [addRole, setAddRole] = useState("");
  const [showStageForm, setShowStageForm] = useState(false);
  const [stageForm, setStageForm] = useState(emptyStageForm);

  const selectedRoute = routes.find((r) => r.id === selectedRouteId) || routes[0] || null;

  const loadStages = useCallback(async () => {
    try {
      const data = await api.mesGetStages();
      setStages(data.stages || []);
    } catch {
      setStages([]);
    }
  }, []);

  const loadRoutes = useCallback(async () => {
    setError("");
    try {
      const data = await api.mesGetTemplateRoutes(templateId);
      const list = data.routes || [];
      setRoutes(list);
      setSelectedRouteId((prev) => {
        if (prev && list.some((r) => r.id === prev)) return prev;
        return list[0]?.id ?? null;
      });
      const current = list.find((r) => r.id === (selectedRouteId || list[0]?.id)) || list[0];
      onRouteChange?.(current || null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [templateId, onRouteChange]);

  useEffect(() => {
    setLoading(true);
    loadRoutes();
    if (!readOnly) loadStages();
  }, [loadRoutes, loadStages, readOnly]);

  useEffect(() => {
    onRouteChange?.(selectedRoute || null);
  }, [selectedRoute, onRouteChange]);

  const refreshRoute = async (routeId) => {
    const detail = await api.mesGetTemplateRoute(templateId, routeId);
    setRoutes((prev) => prev.map((r) => (r.id === routeId ? detail : r)));
    onRouteChange?.(detail);
  };

  const createRoute = async () => {
    if (!newRouteName.trim()) return;
    try {
      const route = await api.mesCreateTemplateRoute(templateId, {
        name: newRouteName.trim(),
        is_default: routes.length === 0,
      });
      setNewRouteName("");
      await loadRoutes();
      setSelectedRouteId(route.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const createVersion = async () => {
    if (!selectedRoute) return;
    try {
      const route = await api.mesCreateRouteVersion(templateId, selectedRoute.id);
      await loadRoutes();
      setSelectedRouteId(route.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const setDefault = async () => {
    if (!selectedRoute) return;
    try {
      await api.mesSetDefaultRoute(templateId, selectedRoute.id);
      await loadRoutes();
    } catch (e) {
      setError(e.message);
    }
  };

  const removeRoute = async () => {
    if (!selectedRoute) return;
    if (!window.confirm(`${selectedRoute.name} v${selectedRoute.version} — ${t("mes.confirmDelete")}?`)) {
      return;
    }
    try {
      await api.mesDeleteTemplateRoute(templateId, selectedRoute.id);
      await loadRoutes();
    } catch (e) {
      setError(e.message);
    }
  };

  const addStep = async () => {
    if (!selectedRoute || !addStageId) return;
    const stage = stages.find((s) => s.id === Number(addStageId));
    try {
      await api.mesAddRouteStep(templateId, selectedRoute.id, {
        stage_id: Number(addStageId),
        department: addDepartment.trim() || stage?.department || undefined,
        responsible_role: addRole.trim() || undefined,
        estimated_minutes: addMinutes ? Number(addMinutes) : undefined,
      });
      setAddStageId("");
      setAddMinutes("");
      setAddDepartment("");
      setAddRole("");
      await refreshRoute(selectedRoute.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const createStage = async (e) => {
    e.preventDefault();
    if (!stageForm.name.trim()) return;
    try {
      const stage = await api.mesCreateStage({
        name: stageForm.name.trim(),
        department: stageForm.department.trim() || "Admin",
      });
      setStageForm(emptyStageForm);
      setShowStageForm(false);
      await loadStages();
      setAddStageId(String(stage.id));
    } catch (err) {
      setError(err.message);
    }
  };

  const removeStep = async (step) => {
    if (!selectedRoute) return;
    if (!window.confirm(`${step.stage_name} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeleteRouteStep(templateId, selectedRoute.id, step.id);
      await refreshRoute(selectedRoute.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const updateStepField = async (step, patch) => {
    if (!selectedRoute) return;
    try {
      await api.mesUpdateRouteStep(templateId, selectedRoute.id, step.id, patch);
      await refreshRoute(selectedRoute.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const reorderSteps = async (fromIndex, toIndex) => {
    if (!selectedRoute || fromIndex === toIndex) return;
    const steps = [...(selectedRoute.steps || [])];
    const [item] = steps.splice(fromIndex, 1);
    steps.splice(toIndex, 0, item);
    const payload = steps.map((step, idx) => ({ id: step.id, step_order: idx }));
    try {
      const route = await api.mesReorderRouteSteps(templateId, selectedRoute.id, payload);
      setRoutes((prev) => prev.map((r) => (r.id === route.id ? route : r)));
      onRouteChange?.(route);
    } catch (e) {
      setError(e.message);
    }
  };

  const onDragStart = (index) => {
    if (readOnly) return;
    setDragIndex(index);
  };

  const onDrop = (index) => {
    if (readOnly || dragIndex === null) return;
    reorderSteps(dragIndex, index);
    setDragIndex(null);
  };

  if (loading) {
    return <p className="py-6 text-center text-sm text-[var(--brand-muted)]">{t("common.loading")}</p>;
  }

  if (readOnly) {
    return <MesRouteTimeline route={selectedRoute} />;
  }

  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-bold">{t("mes.routeDesigner")}</h3>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={createVersion} disabled={!selectedRoute} className="rounded-lg border px-3 py-1.5 text-sm font-semibold disabled:opacity-40">
            {t("mes.newVersion")}
          </button>
          <button type="button" onClick={setDefault} disabled={!selectedRoute || selectedRoute?.is_default} className="rounded-lg border px-3 py-1.5 text-sm font-semibold disabled:opacity-40">
            {t("mes.setDefaultRoute")}
          </button>
          <button type="button" onClick={removeRoute} disabled={!selectedRoute} className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-600 disabled:opacity-40">
            {t("mes.deleteRoute")}
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {routes.map((route) => (
          <button
            key={route.id}
            type="button"
            onClick={() => setSelectedRouteId(route.id)}
            className={`rounded-xl border px-3 py-2 text-sm font-semibold ${
              route.id === selectedRoute?.id ? "ring-2 ring-[var(--brand-primary)]" : ""
            }`}
          >
            {route.name} v{route.version}
            {route.is_default ? " ★" : ""}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          value={newRouteName}
          onChange={(e) => setNewRouteName(e.target.value)}
          placeholder={t("mes.newRouteName")}
          className="rounded-xl border px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={createRoute}
          className="rounded-xl px-4 py-2 text-sm font-bold text-white"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {t("mes.addRoute")}
        </button>
      </div>

      {selectedRoute ? (
        <>
          <div className="mb-4 rounded-xl border bg-gray-50 p-4">
            <p className="mb-2 text-sm font-semibold">{t("mes.addRouteStep")}</p>
            <div className="flex flex-wrap gap-2">
              <select
                value={addStageId}
                onChange={(e) => {
                  setAddStageId(e.target.value);
                  const stage = stages.find((s) => s.id === Number(e.target.value));
                  if (stage && !addDepartment) setAddDepartment(stage.department || "");
                }}
                className="min-w-[180px] flex-1 rounded-xl border px-3 py-2 text-sm"
              >
                <option value="">{t("mes.selectStage")}</option>
                {stages.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.department})
                  </option>
                ))}
              </select>
              <input
                value={addDepartment}
                onChange={(e) => setAddDepartment(e.target.value)}
                placeholder={t("mes.department")}
                className="w-28 rounded-xl border px-3 py-2 text-sm"
              />
              <input
                value={addRole}
                onChange={(e) => setAddRole(e.target.value)}
                placeholder={t("mes.responsibleRole")}
                className="w-28 rounded-xl border px-3 py-2 text-sm"
              />
              <input
                type="number"
                min="0"
                value={addMinutes}
                onChange={(e) => setAddMinutes(e.target.value)}
                placeholder={t("mes.estimatedMinutes")}
                className="w-24 rounded-xl border px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={addStep}
                disabled={!addStageId}
                className="rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                {t("mes.addStep")}
              </button>
              <button
                type="button"
                onClick={() => setShowStageForm((v) => !v)}
                className="rounded-xl border px-3 py-2 text-sm font-semibold"
              >
                {t("mes.addCustomStage")}
              </button>
            </div>
            {showStageForm && (
              <form onSubmit={createStage} className="mt-3 flex flex-wrap gap-2">
                <input
                  value={stageForm.name}
                  onChange={(e) => setStageForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={t("mes.stageName")}
                  className="rounded-xl border px-3 py-2 text-sm"
                  required
                />
                <input
                  value={stageForm.department}
                  onChange={(e) => setStageForm((f) => ({ ...f, department: e.target.value }))}
                  placeholder={t("mes.department")}
                  className="rounded-xl border px-3 py-2 text-sm"
                />
                <button type="submit" className="rounded-xl border px-3 py-2 text-sm font-semibold">
                  {t("mes.saveStage")}
                </button>
              </form>
            )}
          </div>

          {(selectedRoute.steps || []).length === 0 ? (
            <p className="py-6 text-center text-[var(--brand-muted)]">{t("mes.emptyRouteSteps")}</p>
          ) : (
            <ul className="space-y-2">
              {(selectedRoute.steps || []).map((step, index) => (
                <li
                  key={step.id}
                  draggable
                  onDragStart={() => onDragStart(index)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => onDrop(index)}
                  className={`flex flex-wrap items-start gap-3 rounded-xl border p-3 ${
                    dragIndex === index ? "opacity-50" : ""
                  }`}
                >
                  <span className="cursor-grab select-none pt-2 text-lg text-[var(--brand-muted)]" title={t("mes.dragReorder")}>
                    ⠿
                  </span>
                  <span className="pt-2 font-mono text-sm text-[var(--brand-muted)]">{index + 1}</span>
                  <div className="min-w-[140px] flex-1">
                    <p className="font-bold">{step.stage_name}</p>
                    <p className="text-xs text-[var(--brand-muted)]">{step.department}</p>
                  </div>
                  <input
                    type="text"
                    defaultValue={step.responsible_role || ""}
                    placeholder={t("mes.responsibleRole")}
                    onBlur={(e) => {
                      if (e.target.value !== (step.responsible_role || "")) {
                        updateStepField(step, { responsible_role: e.target.value });
                      }
                    }}
                    className="w-28 rounded border px-2 py-1 text-sm"
                  />
                  <input
                    type="number"
                    min="0"
                    defaultValue={step.estimated_minutes ?? ""}
                    placeholder={t("mes.estimatedMinutes")}
                    onBlur={(e) => {
                      const val = e.target.value === "" ? null : Number(e.target.value);
                      if (val !== step.estimated_minutes) {
                        updateStepField(step, { estimated_minutes: val });
                      }
                    }}
                    className="w-20 rounded border px-2 py-1 text-sm"
                  />
                  <input
                    type="number"
                    min="0"
                    defaultValue={step.required_parts_count ?? 0}
                    title={t("mes.requiredParts")}
                    onBlur={(e) => {
                      const val = Number(e.target.value);
                      if (!Number.isNaN(val) && val !== step.required_parts_count) {
                        updateStepField(step, { required_parts_count: val });
                      }
                    }}
                    className="w-16 rounded border px-2 py-1 text-sm"
                  />
                  <button type="button" onClick={() => removeStep(step)} className="text-sm text-red-600">
                    {t("mes.delete")}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <p className="mt-4 text-sm text-[var(--brand-muted)]">
            {t("mes.estimatedTotal")}: <strong>{selectedRoute.estimated_total_minutes ?? 0} min</strong>
          </p>
        </>
      ) : (
        <p className="py-6 text-center text-[var(--brand-muted)]">{t("mes.emptyRoutes")}</p>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  );
}
