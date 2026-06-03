import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

const emptyForm = {
  job_number: "",
  customer_name: "",
  order_reference: "",
  template_id: "",
  quantity: "1",
  priority: "normal",
  due_date: "",
};

export default function MesJobFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canManage =
    isAdmin || hasPermission("mes_edit") || hasPermission("mes_jobs_manage");

  const [form, setForm] = useState(emptyForm);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    if (!canManage) return;
    try {
      const tpl = await api.mesGetTemplates();
      setTemplates(tpl.templates || []);
      if (isEdit) {
        const job = await api.mesGetJob(id);
        if (job.status !== "draft") {
          navigate(`/mes/jobs/${id}`);
          return;
        }
        setForm({
          job_number: job.job_number,
          customer_name: job.customer_name || "",
          order_reference: job.order_reference || "",
          template_id: String(job.template_id),
          quantity: String(job.quantity),
          priority: job.priority || "normal",
          due_date: job.due_date ? job.due_date.slice(0, 10) : "",
        });
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canManage, id, isEdit, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.template_id || Number(form.quantity) <= 0) return;
    setSaving(true);
    const body = {
      customer_name: form.customer_name.trim(),
      order_reference: form.order_reference.trim(),
      template_id: Number(form.template_id),
      quantity: Number(form.quantity),
      priority: form.priority,
      due_date: form.due_date ? `${form.due_date}T00:00:00` : null,
    };
    if (form.job_number.trim()) body.job_number = form.job_number.trim();

    try {
      if (isEdit) {
        await api.mesUpdateJob(id, body);
        navigate(`/mes/jobs/${id}`);
      } else {
        const job = await api.mesCreateJob(body);
        navigate(`/mes/jobs/${job.id}`);
      }
    } catch (err) {
      setToast(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (!canManage) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-4">
        <Link
          to={isEdit ? `/mes/jobs/${id}` : "/mes/jobs"}
          className="text-sm text-[var(--brand-primary)] hover:underline"
        >
          ← {t("mes.jobsTitle")}
        </Link>
      </div>

      <PageHeader
        title={isEdit ? t("mes.editJob") : t("mes.addJob")}
        subtitle={t("mes.jobsSubtitle")}
      />

      <form onSubmit={submit} className="max-w-xl space-y-4 rounded-2xl border bg-[var(--brand-card)] p-6">
        {!isEdit && (
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.jobNumber")}</span>
            <input
              value={form.job_number}
              onChange={(e) => setForm((f) => ({ ...f, job_number: e.target.value.toUpperCase() }))}
              placeholder={t("mes.jobNumberAuto")}
              className="mt-1 w-full rounded-xl border px-4 py-2 font-mono uppercase"
            />
          </label>
        )}

        <label className="block">
          <span className="text-sm font-semibold">{t("mes.product")}</span>
          <select
            required
            value={form.template_id}
            onChange={(e) => setForm((f) => ({ ...f, template_id: e.target.value }))}
            className="mt-1 w-full rounded-xl border px-4 py-2"
          >
            <option value="">{t("mes.selectTemplate")}</option>
            {templates.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.code} — {tpl.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold">{t("mes.customerName")}</span>
          <input
            value={form.customer_name}
            onChange={(e) => setForm((f) => ({ ...f, customer_name: e.target.value }))}
            className="mt-1 w-full rounded-xl border px-4 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-semibold">{t("mes.orderReference")}</span>
          <input
            value={form.order_reference}
            onChange={(e) => setForm((f) => ({ ...f, order_reference: e.target.value }))}
            className="mt-1 w-full rounded-xl border px-4 py-2"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.quantity")}</span>
            <input
              type="number"
              min="0.01"
              step="any"
              required
              value={form.quantity}
              onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">{t("mes.priority")}</span>
            <select
              value={form.priority}
              onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              className="mt-1 w-full rounded-xl border px-4 py-2"
            >
              {["low", "normal", "high", "urgent"].map((p) => (
                <option key={p} value={p}>
                  {t(`mes.priority_${p}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-semibold">{t("mes.dueDate")}</span>
          <input
            type="date"
            value={form.due_date}
            onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
            className="mt-1 w-full rounded-xl border px-4 py-2"
          />
        </label>

        <button
          type="submit"
          disabled={saving}
          className="rounded-xl px-6 py-3 font-bold text-white disabled:opacity-50"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          {saving ? t("common.saving") : t("mes.save")}
        </button>
      </form>

      {error && <ErrorAlert message={error} />}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
