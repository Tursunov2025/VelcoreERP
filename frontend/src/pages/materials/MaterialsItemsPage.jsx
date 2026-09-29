import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, uploadUrl } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import Toast from "../../components/ui/Toast";
import MaterialMasterForm from "../../components/materials/MaterialMasterForm";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";

export default function MaterialsItemsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const { t } = useLocale();
  const canView = isAdmin || hasPermission("materials_view");
  const canEdit = isAdmin || hasPermission("materials_edit");

  const [materials, setMaterials] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selected, setSelected] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [search, setSearch] = useState("");
  const loadSequence = useRef(0);

  const load = useCallback(async () => {
    if (!canView) return;
    const sequence = ++loadSequence.current;
    setError("");
    try {
      const [itemsRes, catRes] = await Promise.all([
        api.materialsItems(true),
        api.materialsCategories(),
      ]);
      if (sequence !== loadSequence.current) return;
      setMaterials(itemsRes.materials || []);
      setCategories(catRes.categories || []);
      setError("");
    } catch (e) {
      if (sequence === loadSequence.current) setError(e.message);
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setSelected(null);
    setShowForm(true);
  };

  const openEdit = (mat) => {
    setSelected(mat);
    setShowForm(true);
  };

  const save = async (payload, imageFile = null) => {
    if (!canEdit) return;
    setBusy(true);
    setToast("");
    try {
      let savedMaterial;

      if (selected) {
        savedMaterial = await api.materialsUpdateItem(selected.id, payload);
      } else {
        savedMaterial = await api.materialsCreateItem(payload);
      }

      const materialId = savedMaterial?.id || selected?.id;

      if (imageFile && materialId) {
        await api.materialsUploadImage(materialId, imageFile);
      }

      setShowForm(false);
      await load();
      setToast(t("materials.itemSaved"));
    } catch (e) {
      const translated = e.code ? t(`materialMaster.errors.${e.code}`) : "";
      setToast(translated && !translated.startsWith("materialMaster.") ? translated : t("materialMaster.errors.generic"));
    } finally {
      setBusy(false);
    }
  };

  const normalizedSearch = search.trim().toLocaleLowerCase();

  const filteredMaterials = normalizedSearch
    ? materials.filter((mat) => {
        const profileSize =
          mat.material_type === "PROFILE"
            ? `${mat.width_mm || ""}x${mat.height_mm || ""} Ø${mat.diameter_mm || ""} ${mat.thickness_mm || ""}`
            : "";

        const haystack = [
          mat.code,
          mat.name,
          mat.category_name,
          mat.material_type,
          mat.profile_type,
          mat.width_mm,
          mat.height_mm,
          mat.diameter_mm,
          mat.thickness_mm,
          mat.steel_grade,
          mat.unit,
          profileSize,
        ]
          .filter((value) => value !== null && value !== undefined)
          .join(" ")
          .toLocaleLowerCase();

        return haystack.includes(normalizedSearch);
      })
    : materials;

  if (!canView) {
    return <p className="py-12 text-center text-red-500">{t("materials.noAccess")}</p>;
  }

  return (
    <div className="pb-24">
      <Link to="/materials" className="mb-4 inline-block min-h-[44px] text-sm font-semibold text-[var(--brand-primary)]">
        ← {t("materials.title")}
      </Link>

      <PageHeader title={t("materials.itemsTitle")} subtitle={t("materials.itemsSubtitle")} />

      {loading ? <LoadingSpinner /> : null}
      <ErrorAlert message={error} onRetry={load} />

      <div className="mb-4 rounded-2xl border bg-[var(--brand-card)] p-3 sm:p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Material kodi, nomi, kategoriya yoki razmer bo‘yicha qidiring..."
              className="min-h-[48px] w-full rounded-xl border bg-transparent px-4 pr-10 text-base outline-none focus:ring-2"
              aria-label="Material qidirish"
            />
            {search ? (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 min-h-[40px] min-w-[40px] -translate-y-1/2 rounded-lg text-lg"
                aria-label="Qidiruvni tozalash"
              >
                ×
              </button>
            ) : null}
          </div>
          <div className="shrink-0 text-sm font-semibold text-[var(--brand-muted)]">
            {filteredMaterials.length} / {materials.length}
          </div>
        </div>
      </div>

      {canEdit ? (
        <button
          type="button"
          onClick={openCreate}
          className="mb-4 min-h-[48px] w-full rounded-xl font-bold text-white sm:w-auto sm:px-8"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          + {t("materials.addItem")}
        </button>
      ) : null}

      {showForm && canEdit ? <div className="mb-6"><MaterialMasterForm key={selected?.id || "new"} material={selected} categories={categories} busy={busy} onSubmit={save} onCancel={() => setShowForm(false)} /></div> : null}

      <div className="space-y-2">
        {filteredMaterials.map((mat) => (
          <div
            key={mat.id}
            className={`rounded-xl border p-4 ${mat.low_stock ? "border-red-300 bg-red-50/50" : "bg-[var(--brand-card)]"}`}
          >
            {mat.image_url ? (
              <div className="mb-4 overflow-hidden rounded-2xl border bg-white">
                <img
                  src={uploadUrl(mat.image_url)}
                  alt={mat.name || mat.code || "Material"}
                  className="h-44 w-full object-contain sm:h-52"
                  loading="lazy"
                />
              </div>
            ) : null}

            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-mono text-sm font-bold text-[var(--brand-primary)]">{mat.code}</p>
                <p className="font-bold">{mat.name}</p>
                <p className="text-sm text-[var(--brand-muted)]">
                  {mat.category_name || t("materials.noCategory")} · {t(`materialMaster.types.${mat.material_type || "CONSUMABLE"}`)} · {t(`materialMaster.units.${mat.unit || "dona"}`)}
                </p>
                {mat.material_type === "PROFILE" ? <p className="mt-1 text-xs text-[var(--brand-muted)]">{mat.profile_type ? t(`materialMaster.profiles.${mat.profile_type}`) : "—"} · {mat.width_mm ? `${mat.width_mm}×${mat.height_mm}` : `Ø${mat.diameter_mm}`}×{mat.thickness_mm} mm · {mat.steel_grade || "—"}</p> : null}
              </div>
              {canEdit ? (
                <button
                  type="button"
                  onClick={() => openEdit(mat)}
                  className="min-h-[44px] shrink-0 rounded-xl border px-4 text-sm font-bold"
                >
                  {t("common.edit")}
                </button>
              ) : null}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldCurrentStock")}: </span>
                <strong className={mat.low_stock ? "text-red-600" : ""}>{mat.current_stock}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldMinStock")}: </span>
                <strong>{mat.minimum_stock}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.fieldUnitCost")}: </span>
                <strong>{mat.unit_cost?.toLocaleString()}</strong>
              </div>
              <div>
                <span className="text-[var(--brand-muted)]">{t("materials.inventoryValue")}: </span>
                <strong>{mat.inventory_value?.toLocaleString()}</strong>
              </div>
            </div>
            {mat.material_type === "PROFILE" && mat.length_lot_summary ? <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold"><span className="rounded-full bg-blue-50 px-3 py-1 text-blue-800">{mat.length_lot_summary.total_pieces} {t("materialMaster.units.pcs")}</span><span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-800">{mat.length_lot_summary.total_meters} m</span><span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">{(mat.length_lot_summary.lengths_m || []).join(" / ") || "—"} m</span></div> : null}
          </div>
        ))}

        {!loading && filteredMaterials.length === 0 ? (
          <div className="rounded-2xl border bg-[var(--brand-card)] px-4 py-10 text-center">
            <p className="font-semibold">Qidiruv bo‘yicha material topilmadi</p>
            <p className="mt-1 text-sm text-[var(--brand-muted)]">
              Kod, nom yoki profil razmerini boshqacha yozib ko‘ring.
            </p>
          </div>
        ) : null}
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
