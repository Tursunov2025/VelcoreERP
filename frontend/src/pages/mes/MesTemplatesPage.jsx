import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_BASE } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

function templateImageUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

export default function MesTemplatesPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("mes_view");
  const canEdit = isAdmin || hasPermission("mes_edit");

  const [templates, setTemplates] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    try {
      const [tpl, cats] = await Promise.all([
        api.mesGetTemplates({
          q: debouncedSearch,
          category_id: categoryFilter || undefined,
        }),
        api.mesGetCategories(),
      ]);
      setTemplates(tpl.templates || []);
      setCategories(cats.categories || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canView, debouncedSearch, categoryFilter]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("mes.noAccess")}</p>;
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link to="/mes" className="text-sm text-[var(--brand-primary)] hover:underline">
          ← {t("mes.backHub")}
        </Link>
        {canEdit && (
          <Link
            to="/mes/templates/new"
            className="rounded-xl px-4 py-2 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            + {t("mes.addTemplate")}
          </Link>
        )}
      </div>
      <PageHeader title={t("mes.templatesTitle")} subtitle={t("mes.templatesSubtitle")} />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("mes.searchTemplates")}
          className="flex-1 rounded-xl border px-4 py-3"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-xl border px-4 py-3"
        >
          <option value="">{t("mes.noCategory")}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorAlert message={error} />}
      {loading ? (
        <LoadingSpinner />
      ) : templates.length === 0 ? (
        <p className="text-center text-[var(--brand-muted)]">{t("mes.emptyTemplates")}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {templates.map((tpl) => (
            <Link
              key={tpl.id}
              to={`/mes/templates/${tpl.id}`}
              className="flex gap-4 rounded-2xl border bg-[var(--brand-card)] p-4 transition hover:border-[var(--brand-primary)]"
            >
              <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-gray-100">
                {tpl.image_url ? (
                  <img
                    src={templateImageUrl(tpl.image_url)}
                    alt={tpl.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-2xl text-gray-400">📦</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-[var(--brand-muted)]">{tpl.code}</p>
                <h3 className="truncate font-bold">{tpl.name}</h3>
                <p className="text-sm text-[var(--brand-muted)]">
                  {tpl.category_name || t("mes.noCategory")}
                </p>
                <div className="mt-2 flex gap-2 text-xs">
                  <span className="rounded bg-gray-100 px-2 py-0.5">BOM {tpl.bom_count}</span>
                  <span className="rounded bg-gray-100 px-2 py-0.5">
                    {t("mes.routeCount")} {tpl.route_count}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
