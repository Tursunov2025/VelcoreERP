import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import Card from "../../components/ui/Card";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useLocale } from "../../context/LocaleContext";

function fmtDate(v) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
}

export default function PackagePassportPage() {
  const { labelCode } = useParams();
  const { t } = useLocale();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reprintBusy, setReprintBusy] = useState(false);
  const [reprintMsg, setReprintMsg] = useState("");

  useEffect(() => {
    if (!labelCode) return;
    setLoading(true);
    setError("");
    api
      .packagePassport(labelCode)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [labelCode]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div>
        <PageHeader title={t("traceability.passportTitle")} />
        <ErrorAlert message={error || t("traceability.notFound")} />
        <Link to="/scanner" className="mt-4 inline-block text-sm text-blue-600 hover:underline">
          {t("traceability.openScanner")}
        </Link>
      </div>
    );
  }

  const loc = data.location || {};

  return (
    <div>
      <PageHeader
        title={data.label_code}
        subtitle={t("traceability.passportSubtitle")}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("traceability.details")}</h2>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.product")}</dt>
              <dd className="font-semibold">{data.product || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">SKU</dt>
              <dd className="font-semibold">{data.sku || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.weight")}</dt>
              <dd className="font-semibold">{data.weight_kg} kg</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.dimensions")}</dt>
              <dd className="font-semibold">
                {data.length_mm ?? "—"} × {data.width_mm ?? "—"} × {data.height_mm ?? "—"} mm
              </dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.customer")}</dt>
              <dd className="font-semibold">{data.customer || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.jobNumber")}</dt>
              <dd className="font-semibold">{data.job_number || "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.productionDate")}</dt>
              <dd className="font-semibold">{fmtDate(data.production_date)}</dd>
            </div>
            <div>
              <dt className="text-[var(--brand-muted)]">{t("traceability.status")}</dt>
              <dd className="font-semibold">{data.status}</dd>
            </div>
          </dl>
          <div className="mt-4 rounded-xl bg-gray-50 p-3 text-sm">
            <p className="font-semibold">{t("traceability.location")}</p>
            <p>
              {loc.warehouse_zone || "—"} / {loc.rack || "—"} / {loc.shelf || "—"}
              {loc.location_code ? ` (${loc.location_code})` : ""}
            </p>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("traceability.label")}</h2>
          <div className="flex flex-wrap gap-6">
            {data.qr_image_base64 ? (
              <img
                src={`data:image/png;base64,${data.qr_image_base64}`}
                alt="QR"
                className="h-40 w-40 rounded-lg border bg-white p-2"
              />
            ) : null}
            {data.barcode_image_base64 ? (
              <img
                src={`data:image/png;base64,${data.barcode_image_base64}`}
                alt="Barcode"
                className="h-24 max-w-full rounded-lg border bg-white p-2"
              />
            ) : null}
          </div>
          {data.printed_at ? (
            <p className="mt-3 text-xs text-[var(--brand-muted)]">
              {t("traceability.printed")}: {fmtDate(data.printed_at)} ({data.printer_name || "—"})
            </p>
          ) : null}
          <button
            type="button"
            disabled={reprintBusy}
            onClick={async () => {
              setReprintBusy(true);
              setReprintMsg("");
              try {
                const job = await api.packageReprintLabel(data.label_code);
                setReprintMsg(
                  `${t("printing.reprintQueued")} (#${job.id}, ${job.status})`
                );
              } catch (e) {
                setReprintMsg(e.message);
              } finally {
                setReprintBusy(false);
              }
            }}
            className="mt-4 w-full rounded-2xl border-2 border-black px-4 py-3 text-sm font-bold disabled:opacity-50"
          >
            {reprintBusy ? t("common.saving") : t("printing.reprintLabel")}
          </button>
          {reprintMsg ? (
            <p className="mt-2 text-xs font-semibold text-[var(--brand-muted)]">{reprintMsg}</p>
          ) : null}
        </Card>
      </div>
      <Card className="mt-4">
        <h2 className="mb-4 text-lg font-bold">{t("traceability.timeline")}</h2>
        <ul className="space-y-3">
          {(data.timeline || []).map((step) => (
            <li
              key={step.stage_key}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-3"
            >
              <span className="font-semibold">{step.stage_name}</span>
              <span className="text-sm text-[var(--brand-muted)]">
                {step.operator || "—"} · {fmtDate(step.completed_at || step.started_at)}
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <Link
        to={`/track/package/${encodeURIComponent(data.label_code)}`}
        className="mt-4 inline-block text-sm text-blue-600 hover:underline"
        target="_blank"
        rel="noreferrer"
      >
        {t("traceability.publicLink")}
      </Link>
    </div>
  );
}
