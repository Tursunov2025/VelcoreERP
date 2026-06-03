import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, API_BASE } from "../../api/client";
import MesBomEditor from "../../components/mes/MesBomEditor";
import MesRouteDesigner from "../../components/mes/MesRouteDesigner";
import MesDrawingsGallery from "../../components/mes/MesDrawingsGallery";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import { useMobileReadOnly } from "../../hooks/useMobileReadOnly";

function resolveImageUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

function formatQty(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "0";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
      <p className="text-sm text-[var(--brand-muted)]">{label}</p>
      <p className="mt-1 text-3xl font-black">{value}</p>
      {hint && <p className="mt-1 text-xs text-[var(--brand-muted)]">{hint}</p>}
    </div>
  );
}

export default function MesTemplateDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("mes_view");
  const canEdit = isAdmin || hasPermission("mes_edit");
  const canDelete = isAdmin || hasPermission("mes_delete");
  const canDesignRoutes = isAdmin || hasPermission("mes_edit") || hasPermission("mes_routes_design");
  const canUploadDrawings = isAdmin || hasPermission("mes_edit") || hasPermission("mes_drawings_upload");
  const mobileReadOnly = useMobileReadOnly();
  const bomReadOnly = mobileReadOnly || !canEdit;
  const routeReadOnly = mobileReadOnly || !canDesignRoutes;
  const drawingsReadOnly = mobileReadOnly || !canUploadDrawings;

  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [dupCode, setDupCode] = useState("");
  const [showDup, setShowDup] = useState(false);
  const [bomSummary, setBomSummary] = useState(null);
  const [routeSummary, setRouteSummary] = useState(null);
  const [drawingCount, setDrawingCount] = useState(0);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const tpl = await api.mesGetTemplate(id);
      setTemplate(tpl);
      setBomSummary(tpl.bom_summary || null);
      setRouteSummary(tpl.route_summary || null);
      setDrawingCount(tpl.drawing_count ?? 0);
      setDupCode(`${tpl.code}-COPY`);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, id]);

  useEffect(() => {
    load();
  }, [load]);

  const uploadImage = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !canEdit) return;
    try {
      const updated = await api.mesUploadTemplateImage(id, file);
      setTemplate(updated);
      setToast(t("mes.uploadImage"));
    } catch (err) {
      setToast(err.message);
    }
  };

  const duplicate = async () => {
    if (!dupCode.trim()) return;
    try {
      const copy = await api.mesDuplicateTemplate(id, dupCode.trim());
      setToast(t("mes.duplicate"));
      navigate(`/mes/templates/${copy.id}`);
    } catch (err) {
      setToast(err.message);
    }
  };

  const remove = async () => {
    if (!window.confirm(`${template.code} — ${t("mes.confirmDelete")}?`)) return;
    try {
      await api.mesDeleteTemplate(id);
      navigate("/mes/templates");
    } catch (err) {
      setToast(err.message);
    }
  };

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;
  if (!template) return <ErrorAlert message={error || "Not found"} />;

  const img = resolveImageUrl(template.image_url);
  const summary = bomSummary || template.bom_summary || {};
  const routes = routeSummary || template.route_summary || {};

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link to="/mes/templates" className="text-sm text-[var(--brand-primary)] hover:underline">
          ← {t("mes.templatesTitle")}
        </Link>
        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <Link
              to={`/mes/templates/${id}/edit`}
              className="rounded-xl border px-4 py-2 text-sm font-semibold"
            >
              {t("mes.editTemplate")}
            </Link>
          )}
          {canEdit && (
            <button
              type="button"
              onClick={() => setShowDup((v) => !v)}
              className="rounded-xl border px-4 py-2 text-sm font-semibold"
            >
              {t("mes.duplicate")}
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              onClick={remove}
              className="rounded-xl border border-red-200 px-4 py-2 text-sm font-semibold text-red-600"
            >
              {t("mes.delete")}
            </button>
          )}
        </div>
      </div>

      <PageHeader
        title={template.name}
        subtitle={`${template.code}${template.category_name ? ` · ${template.category_name}` : ""}`}
      />

      {showDup && canEdit && (
        <div className="mb-4 flex flex-wrap gap-2 rounded-xl border bg-amber-50 p-4">
          <input
            value={dupCode}
            onChange={(e) => setDupCode(e.target.value.toUpperCase())}
            placeholder={t("mes.duplicateCode")}
            className="rounded-xl border px-4 py-2 font-mono uppercase"
          />
          <button
            type="button"
            onClick={duplicate}
            className="rounded-xl px-4 py-2 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            {t("mes.duplicate")}
          </button>
        </div>
      )}

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label={t("mes.bomPartsCount")} value={summary.parts_count ?? template.bom_count ?? 0} />
        <StatCard
          label={t("mes.totalRequired")}
          value={formatQty(summary.total_required_quantity ?? 0)}
        />
        <StatCard
          label={t("mes.totalProduced")}
          value={formatQty(summary.total_produced_quantity ?? 0)}
        />
        <StatCard
          label={t("mes.totalAccepted")}
          value={formatQty(summary.total_accepted_quantity ?? 0)}
        />
        <StatCard
          label={t("mes.totalRejected")}
          value={formatQty(summary.total_rejected_quantity ?? 0)}
        />
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("mes.routeCount")} value={routes.route_count ?? template.route_count ?? 0} />
        <StatCard
          label={t("mes.defaultRoute")}
          value={
            routes.default_route_name
              ? `${routes.default_route_name}${routes.default_route_version ? ` v${routes.default_route_version}` : ""}`
              : "—"
          }
        />
        <StatCard
          label={t("mes.estimatedTotal")}
          value={`${routes.estimated_total_minutes ?? template.estimated_total_minutes ?? 0} min`}
        />
        <StatCard label={t("mes.drawingCount")} value={drawingCount} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <div className="rounded-2xl border bg-[var(--brand-card)] p-4">
          <div className="flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-gray-100">
            {img ? (
              <img src={img} alt={template.name} className="h-full w-full object-cover" />
            ) : (
              <span className="text-4xl text-gray-300">📦</span>
            )}
          </div>
          {canEdit && (
            <div className="mt-3">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={uploadImage}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="w-full rounded-xl border py-2 text-sm font-semibold"
              >
                {img ? t("mes.changeImage") : t("mes.uploadImage")}
              </button>
            </div>
          )}
        </div>

        <div className="rounded-2xl border bg-[var(--brand-card)] p-6">
          <h3 className="mb-4 text-lg font-bold">{t("mes.basicInfo")}</h3>
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.templateCode")}</dt>
              <dd className="font-mono font-semibold">{template.code}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.category")}</dt>
              <dd>{template.category_name || t("mes.noCategory")}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.qrPrefix")}</dt>
              <dd className="font-mono">{template.qr_prefix || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.active")}</dt>
              <dd>{template.is_active ? "✓" : "—"}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.description")}</dt>
              <dd>{template.description || "—"}</dd>
            </div>
          </dl>

          <h3 className="mb-3 mt-6 text-lg font-bold">{t("mes.dimensions")}</h3>
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.lengthMm")}</dt>
              <dd>{template.length_mm ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.widthMm")}</dt>
              <dd>{template.width_mm ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.heightMm")}</dt>
              <dd>{template.height_mm ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--brand-muted)]">{t("mes.weightKg")}</dt>
              <dd>{template.weight_kg ?? "—"}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-6">
        <MesBomEditor
          templateId={id}
          readOnly={bomReadOnly}
          onSummaryChange={setBomSummary}
        />
      </div>

      <div className="mt-6">
        <MesRouteDesigner
          templateId={id}
          readOnly={routeReadOnly}
          onRouteChange={(route) => {
            if (!route) return;
            setRouteSummary((prev) => ({
              ...(prev || {}),
              route_count: prev?.route_count ?? template.route_count,
              default_route_id: route.is_default ? route.id : prev?.default_route_id,
              default_route_name: route.is_default ? route.name : prev?.default_route_name,
              default_route_version: route.is_default ? route.version : prev?.default_route_version,
              estimated_total_minutes: route.is_default
                ? route.estimated_total_minutes
                : prev?.estimated_total_minutes,
            }));
          }}
        />
      </div>

      <div className="mt-6">
        <MesDrawingsGallery
          templateId={id}
          readOnly={drawingsReadOnly}
          onCountChange={setDrawingCount}
        />
      </div>

      {error && <ErrorAlert message={error} />}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
