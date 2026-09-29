import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { api, uploadUrl } from "../../api/client";
import { useLocale } from "../../context/LocaleContext";

const tabs = ["general", "branding", "localization", "business", "contacts", "regional"];
const defaults = {
  company_name: "",
  short_name: "",
  registration_number: "",
  tin: "",
  website: "",
  industry: "",
  fiscal_year: "January–December",
  logo_url: "",
  dark_logo_url: "",
  favicon_url: "",
  login_background_url: "",
  watermark_url: "",
  language: "uz",
  timezone: "Asia/Tashkent",
  currency: "UZS",
  date_format: "DD.MM.YYYY",
  number_format: "1 234,56",
  measurement_units: "metric",
  working_days: ["monday", "tuesday", "wednesday", "thursday", "friday"],
  working_hours_start: "09:00",
  working_hours_end: "18:00",
  weekend_configuration: "Saturday and Sunday",
  production_shifts: "1",
  default_warehouse: "",
  default_tax: "",
  phone: "",
  email: "",
  support_email: "",
  telegram: "",
  whatsapp: "",
  address: "",
  google_maps_location: "",
  country: "Uzbekistan",
  region: "",
  city: "",
  postal_code: "",
};
const inputClass =
  "w-full rounded-xl border border-[var(--brand-muted)]/30 bg-transparent px-3 py-2.5 text-sm text-[var(--brand-text)] outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary)]/20";

function Field({ label, error, children, wide = false }) {
  return (
    <label
      className={`block text-sm font-medium text-[var(--brand-text)] ${wide ? "sm:col-span-2" : ""}`}
    >
      <span className="mb-1.5 block">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-red-500">{error.message}</span>
      ) : null}
    </label>
  );
}
function Card({ title, description, children }) {
  return (
    <section className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm sm:p-7">
      <h2 className="text-lg font-black text-[var(--brand-text)]">{title}</h2>
      <p className="mt-1 text-sm text-[var(--brand-muted)]">{description}</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  );
}
function Asset({ label, field, url, busy, onUpload }) {
  const { t } = useLocale();
  return (
    <div className="rounded-2xl border border-dashed border-[var(--brand-muted)]/35 p-4">
      <p className="capitalize text-sm font-semibold text-[var(--brand-text)]">
        {label}
      </p>
      <div className="mt-3 flex items-center gap-3">
        {url ? (
          <img
            src={uploadUrl(url)}
            alt=""
            className="h-12 w-12 rounded-lg border object-contain"
          />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/5">
            ⌁
          </div>
        )}
        <label className="cursor-pointer rounded-xl border border-[var(--brand-muted)]/30 px-3 py-2 text-xs font-bold hover:bg-black/5">
          {busy ? t("organization.uploading") : t("organization.chooseFile")}
          <input
            className="sr-only"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml,image/x-icon"
            disabled={busy}
            onChange={(e) => onUpload(field, e.target.files?.[0])}
          />
        </label>
      </div>
    </div>
  );
}

export default function OrganizationTab() {
  const { t } = useLocale();
  const [tab, setTab] = useState("general");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autosave, setAutosave] = useState(true);
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState("");
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isDirty },
  } = useForm({ defaultValues: defaults });
  const values = watch();

  const save = async (data) => {
    setSaving(true);
    setMessage("");
    try {
      const saved = await api.updateOrganizationSettings(data);
      reset({ ...defaults, ...saved });
      setMessage(t("organization.saved"));
    } catch (error) {
      setMessage(error.message || t("errors.generic"));
    } finally {
      setSaving(false);
    }
  };
  useEffect(() => {
    let alive = true;
    api
      .organizationSettings()
      .then((data) => alive && reset({ ...defaults, ...data }))
      .catch((e) => setMessage(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [reset]);
  useEffect(() => {
    const warn = (event) => {
      if (isDirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isDirty]);
  useEffect(() => {
    if (!autosave || !isDirty || loading || saving) return undefined;
    const id = window.setTimeout(() => handleSubmit(save)(), 1200);
    return () => window.clearTimeout(id);
  }, [autosave, isDirty, loading, saving, values, handleSubmit]);
  const upload = async (field, file) => {
    if (!file) return;
    setUploading(field);
    try {
      const result = await api.uploadOrganizationAsset(file);
      setValue(field, result.url, { shouldDirty: true });
    } catch (error) {
      setMessage(error.message || t("errors.generic"));
    } finally {
      setUploading("");
    }
  };
  if (loading)
    return (
      <div className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-8 text-sm text-[var(--brand-muted)]">
        {t("common.loading")}
      </div>
    );

  return (
    <div className="space-y-5">
      <header className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand-muted)]">
              {t("organization.title")}
            </p>
            <h2 className="mt-1 text-2xl font-black text-[var(--brand-text)]">
              {t("organization.enterpriseProfile")}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-[var(--brand-muted)]">
              <input
                type="checkbox"
                checked={autosave}
                onChange={(e) => setAutosave(e.target.checked)}
              />{" "}
                {t("organization.autosave")}
            </label>
            <button
              type="button"
              onClick={handleSubmit(save)}
              disabled={saving}
              className="rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60"
            >
              {saving ? t("common.saving") : t("organization.saveChanges")}
            </button>
          </div>
        </div>
        {message ? (
          <p className="mt-4 text-sm text-[var(--brand-muted)]">{message}</p>
        ) : null}
      </header>
      <nav
        className="flex gap-2 overflow-x-auto pb-1"
        aria-label={t("platformAdministration.organizationSections")}
      >
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setTab(name)}
            className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-bold ${tab === name ? "bg-[var(--brand-secondary)] text-[var(--brand-primary)]" : "bg-[var(--brand-card)] text-[var(--brand-muted)]"}`}
          >
            {t(`organization.${name}`)}
          </button>
        ))}
      </nav>
      <form onSubmit={handleSubmit(save)}>
        {tab === "general" && (
          <Card
            title={t("organization.general")}
            description={t("organization.generalDescription")}
          >
            <Field label={t("organization.companyName")} error={errors.company_name}>
              <input
                className={inputClass}
                {...register("company_name", {
                  required: t("validation.required", { field: t("organization.companyName") }),
                  maxLength: { value: 160, message: t("validation.maxLength", { max: 160 }) },
                })}
              />
            </Field>
            <Field label={t("organization.shortName")}>
              <input
                className={inputClass}
                {...register("short_name", { maxLength: 80 })}
              />
            </Field>
            <Field label={t("organization.registrationNumber")}>
              <input
                className={inputClass}
                {...register("registration_number", { maxLength: 80 })}
              />
            </Field>
            <Field label={t("organization.tin")}>
              <input
                className={inputClass}
                {...register("tin", { maxLength: 64 })}
              />
            </Field>
            <Field label={t("organization.website")} error={errors.website}>
              <input
                className={inputClass}
                placeholder="https://example.com"
                {...register("website", {
                  pattern: {
                    value: /^(https?:\/\/)?[^\s]+\.[^\s]+$/,
                    message: t("validation.invalidUrl"),
                  },
                })}
              />
            </Field>
            <Field label={t("organization.industry")}>
              <input
                className={inputClass}
                {...register("industry", { maxLength: 100 })}
              />
            </Field>
            <Field label={t("organization.fiscalYear")}>
              <select className={inputClass} {...register("fiscal_year")}>
                <option value="January–December">{t("organization.januaryDecember")}</option>
                <option value="April–March">{t("organization.aprilMarch")}</option>
                <option value="July–June">{t("organization.julyJune")}</option>
              </select>
            </Field>
          </Card>
        )}
        {tab === "branding" && (
          <div className="space-y-5">
            <Card
              title={t("platformAdministration.brandingAssets")}
              description={t("organization.brandingDescription")}
            >
              {[
                  [t("organization.companyLogo"), "logo_url"], [t("organization.darkLogo"), "dark_logo_url"], [t("organization.favicon"), "favicon_url"], [t("organization.loginBackground"), "login_background_url"], [t("organization.watermark"), "watermark_url"],
              ].map(([label, field]) => (
                <Asset
                  key={field}
                  label={label}
                  field={field}
                  url={values[field]}
                  busy={uploading === field}
                  onUpload={upload}
                />
              ))}
            </Card>
            <Card
              title={t("platformAdministration.preview")}
              description={t("organization.brandingDescription")}
            >
              <div className="sm:col-span-2 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl bg-[var(--brand-primary)] p-5 text-white">
                  {values.logo_url ? (
                    <img
                      src={uploadUrl(values.logo_url)}
                        alt={t("organization.companyLogo")}
                      className="h-10 max-w-full object-contain object-left"
                    />
                  ) : (
                    <strong>{values.company_name || t("organization.company")}</strong>
                  )}
                  <p className="mt-8 text-sm opacity-75">{t("platformAdministration.navigationPreview")}</p>
                </div>
                <div
                  className="min-h-32 rounded-xl bg-black/75 p-5 text-white"
                  style={
                    values.login_background_url
                      ? {
                          backgroundImage: `linear-gradient(#0008,#0008), url(${uploadUrl(values.login_background_url)})`,
                          backgroundSize: "cover",
                        }
                      : undefined
                  }
                >
                  {values.dark_logo_url ? (
                    <img
                      src={uploadUrl(values.dark_logo_url)}
                        alt={t("organization.darkLogo")}
                      className="h-10 max-w-full object-contain object-left"
                    />
                  ) : (
                    <strong>{values.company_name || t("organization.company")}</strong>
                  )}
                  <p className="mt-8 text-sm opacity-75">{t("platformAdministration.loginPreview")}</p>
                </div>
              </div>
            </Card>
          </div>
        )}
        {tab === "localization" && (
          <Card
            title={t("organization.localization")}
            description={t("organization.localizationDescription")}
          >
            <Field label={t("organization.language")}>
              <select className={inputClass} {...register("language")}>
                <option value="uz">{t("organization.uzbekLatin")}</option>
                <option value="ru">{t("organization.russian")}</option>
              </select>
            </Field>
            <Field label={t("organization.timezone")}>
              <select className={inputClass} {...register("timezone")}>
                <option>Asia/Tashkent</option>
                <option>UTC</option>
              </select>
            </Field>
            <Field label={t("organization.currency")}>
              <input
                className={inputClass}
                {...register("currency", {
                  required: t("validation.required", { field: t("organization.currency") }),
                  maxLength: 3,
                })}
              />
            </Field>
            <Field label={t("organization.dateFormat")}>
              <select className={inputClass} {...register("date_format")}>
                <option>DD.MM.YYYY</option>
                <option>MM/DD/YYYY</option>
                <option>YYYY-MM-DD</option>
              </select>
            </Field>
            <Field label={t("organization.numberFormat")}>
              <select className={inputClass} {...register("number_format")}>
                <option>1 234,56</option>
                <option>1,234.56</option>
              </select>
            </Field>
            <Field label={t("organization.measurementUnits")}>
              <select className={inputClass} {...register("measurement_units")}>
                <option value="metric">{t("platformAdministration.metric")}</option>
                <option value="imperial">{t("platformAdministration.imperial")}</option>
              </select>
            </Field>
          </Card>
        )}
        {tab === "business" && (
          <Card
            title={t("platformAdministration.businessOperations")}
            description={t("organization.businessDescription")}
          >
            <div className="sm:col-span-2">
              <p className="mb-2 text-sm font-medium text-[var(--brand-text)]">
                  {t("platformAdministration.workingDays")}
              </p>
              <div className="flex flex-wrap gap-2">
                {[
                  "monday",
                  "tuesday",
                  "wednesday",
                  "thursday",
                  "friday",
                  "saturday",
                  "sunday",
                ].map((day) => (
                  <label
                    key={day}
                    className="rounded-xl border border-[var(--brand-muted)]/30 px-3 py-2 text-sm capitalize"
                  >
                    <input
                      className="mr-2"
                      type="checkbox"
                      value={day}
                      {...register("working_days")}
                    />
                        {t(`weekdays.${day}`)}
                  </label>
                ))}
              </div>
            </div>
            <Field label={t("organization.workingHoursStart")}>
              <input
                className={inputClass}
                type="time"
                {...register("working_hours_start")}
              />
            </Field>
            <Field label={t("organization.workingHoursEnd")}>
              <input
                className={inputClass}
                type="time"
                {...register("working_hours_end")}
              />
            </Field>
            <Field label={t("organization.weekendConfiguration")}>
              <input
                className={inputClass}
                {...register("weekend_configuration")}
              />
            </Field>
            <Field label={t("organization.productionShifts")}>
              <select className={inputClass} {...register("production_shifts")}>
                  <option value="1">1 {t("platformAdministration.shift")}</option>
                  <option value="2">2 {t("platformAdministration.shift")}</option>
                  <option value="3">3 {t("platformAdministration.shift")}</option>
              </select>
            </Field>
            <Field label={t("organization.defaultWarehouse")}>
              <input
                className={inputClass}
                {...register("default_warehouse")}
              />
            </Field>
            <Field label={t("organization.defaultTax")}>
              <input
                className={inputClass}
                placeholder="VAT 12%"
                {...register("default_tax")}
              />
            </Field>
          </Card>
        )}
        {tab === "contacts" && (
          <Card
            title={t("organization.contacts")}
            description={t("organization.contactsDescription")}
          >
            <Field label={t("organization.phone")}>
              <input
                className={inputClass}
                type="tel"
                {...register("phone", { maxLength: 40 })}
              />
            </Field>
            <Field label={t("organization.email")} error={errors.email}>
              <input
                className={inputClass}
                type="email"
                {...register("email", {
                  pattern: {
                    value: /^\S+@\S+\.\S+$/,
                    message: t("validation.invalidEmail"),
                  },
                })}
              />
            </Field>
            <Field label={t("organization.supportEmail")} error={errors.support_email}>
              <input
                className={inputClass}
                type="email"
                {...register("support_email", {
                  pattern: {
                    value: /^\S+@\S+\.\S+$/,
                    message: t("validation.invalidEmail"),
                  },
                })}
              />
            </Field>
            <Field label={t("organization.telegram")}>
              <input
                className={inputClass}
                placeholder="@company"
                {...register("telegram")}
              />
            </Field>
            <Field label={t("organization.whatsapp")}>
              <input
                className={inputClass}
                type="tel"
                {...register("whatsapp")}
              />
            </Field>
            <Field label={t("organization.mapsLocation")}>
              <input
                className={inputClass}
                placeholder="https://maps.google.com/..."
                {...register("google_maps_location")}
              />
            </Field>
            <Field label={t("organization.address")} wide>
              <textarea
                className={inputClass}
                rows="3"
                {...register("address", { maxLength: 300 })}
              />
            </Field>
          </Card>
        )}
        {tab === "regional" && (
          <Card
            title={t("organization.regional")}
            description={t("organization.regionalDescription")}
          >
            <Field label={t("organization.country")} error={errors.country}>
              <input
                className={inputClass}
                {...register("country", { required: t("validation.required", { field: t("organization.country") }) })}
              />
            </Field>
            <Field label={t("organization.region")}>
              <input className={inputClass} {...register("region")} />
            </Field>
            <Field label={t("organization.city")}>
              <input className={inputClass} {...register("city")} />
            </Field>
            <Field label={t("organization.postalCode")}>
              <input
                className={inputClass}
                {...register("postal_code", { maxLength: 20 })}
              />
            </Field>
          </Card>
        )}
      </form>
    </div>
  );
}
