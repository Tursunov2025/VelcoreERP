import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, API_BASE } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const emptyForm = {
  code: "",
  name: "",
  category_id: "",
  description: "",
  length_mm: "",
  width_mm: "",
  height_mm: "",
  weight_kg: "",
  qr_prefix: "",
  is_active: true,
};

function imageUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

export default function MesTemplateFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canEdit = isAdmin || hasPermission("mes_edit");

  const [form, setForm] = useState(emptyForm);
  const [categories, setCategories] = useState([]);
  const [currentImageUrl, setCurrentImageUrl] = useState("");
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canEdit) return;
    try {
      const cats = await api.mesGetCategories();
      setCategories(cats.categories || []);
      if (isEdit) {
        const tpl = await api.mesGetTemplate(id);
        setForm({
          code: tpl.code,
          name: tpl.name,
          category_id: tpl.category_id ?? "",
          description: tpl.description || "",
          length_mm: tpl.length_mm ?? "",
          width_mm: tpl.width_mm ?? "",
          height_mm: tpl.height_mm ?? "",
          weight_kg: tpl.weight_kg ?? "",
          qr_prefix: tpl.qr_prefix || "",
          is_active: tpl.is_active !== false,
        });
        setCurrentImageUrl(tpl.image_url || "");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canEdit, id, isEdit]);

  useEffect(() => {
    load();
  }, [load]);

  const buildBody = () => ({
    code: form.code.trim(),
    name: form.name.trim(),
    category_id: form.category_id ? Number(form.category_id) : null,
    description: form.description,
    length_mm: form.length_mm === "" ? null : Number(form.length_mm),
    width_mm: form.width_mm === "" ? null : Number(form.width_mm),
    height_mm: form.height_mm === "" ? null : Number(form.height_mm),
    weight_kg: form.weight_kg === "" ? null : Number(form.weight_kg),
    qr_prefix: form.qr_prefix.trim() || null,
    is_active: form.is_active,
  });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.code.trim() || !form.name.trim()) return;
    setSaving(true);
    try {
      let templateId = id;
      if (isEdit) {
        await api.mesUpdateTemplate(id, buildBody());
      } else {
        const created = await api.mesCreateTemplate(buildBody());
        templateId = created.id;
      }
      const file = fileRef.current?.files?.[0];
      if (file && templateId) {
        await api.mesUploadTemplateImage(templateId, file);
      }
      navigate(`/mes/templates/${templateId}`);
    } catch (err) {
      setToast(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (!canEdit) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-4">
        <Link
          to={isEdit ? `/mes/templates/${id}` : "/mes/templates"}
          className="text-sm text-[var(--brand-primary)] hover:underline"
        >
          ← {isEdit ? t("mes.templateDetail") : t("mes.templatesTitle")}
        </Link>
      </div>
      <PageHeader
        title={isEdit ? t("mes.editTemplate") : t("mes.addTemplate")}
        subtitle={t("mes.templatesSubtitle")}
      />
      {error && <ErrorAlert message={error} />}

      <form onSubmit={submit} className="grid max-w-3xl gap-4 rounded-2xl border bg-[var(--brand-card)] p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.templateCode")}</span>
            <input
              required
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
              className="mt-1 w-full rounded-xl border px-4 py-2 font-mono uppercase"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.templateName")}</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="text-sm font-semibold">{t("mes.category")}</span>
            <select
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            >
              <option value="">{t("mes.noCategory")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="text-sm font-semibold">{t("mes.description")}</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.lengthMm")}</span>
            <input
              type="number"
              step="any"
              value={form.length_mm}
              onChange={(e) => setForm({ ...form, length_mm: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.widthMm")}</span>
            <input
              type="number"
              step="any"
              value={form.width_mm}
              onChange={(e) => setForm({ ...form, width_mm: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.heightMm")}</span>
            <input
              type="number"
              step="any"
              value={form.height_mm}
              onChange={(e) => setForm({ ...form, height_mm: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.weightKg")}</span>
            <input
              type="number"
              step="any"
              value={form.weight_kg}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="text-sm font-semibold">{t("mes.qrPrefix")}</span>
            <input
              value={form.qr_prefix}
              onChange={(e) => setForm({ ...form, qr_prefix: e.target.value })}
              className="mt-1 w-full rounded-xl border px-4 py-2 font-mono"
            />
          </label>
          <label className="flex items-center gap-2 sm:col-span-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <span>{t("mes.active")}</span>
          </label>
        </div>

        <div>
          <span className="text-sm font-semibold">{t("mes.uploadImage")}</span>
          <div className="mt-2 flex flex-wrap items-center gap-4">
            <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-xl bg-gray-100">
              {currentImageUrl ? (
                <img src={imageUrl(currentImageUrl)} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="text-gray-400">{t("mes.noImage")}</span>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="text-sm" />
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="rounded-xl px-6 py-3 font-bold text-white disabled:opacity-60"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {saving ? t("common.saving") : t("mes.save")}
        </button>
      </form>
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
