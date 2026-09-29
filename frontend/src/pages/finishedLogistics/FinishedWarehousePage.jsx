import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useAuth } from "../../context/AuthContext";
import { useLocale } from "../../context/LocaleContext";
import ProductPassportActions from "../../components/traceability/ProductPassportActions";
import {
  apiMessage,
  date,
  field,
  number,
  panel,
} from "../productionProjects/projectUi";

export default function FinishedWarehousePage() {
  const { t, locale } = useLocale();
  const { hasPermission } = useAuth();
  const [data, setData] = useState({
    inventory: [],
    locations: [],
    totals: {},
  });
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [locationForm, setLocationForm] = useState({
    parent_id: "",
    location_type: "warehouse",
    segment_code: "",
    description: "",
  });
  const load = useCallback(async () => {
    try {
      const [inventory, locations, totals] = await Promise.all([
        api.mesWarehouseInventory(true),
        api.finishedLocations(true),
        api.finishedWarehouseTotals(),
      ]);
      setData({
        inventory: inventory.inventory || inventory.items || [],
        locations: locations.locations || [],
        totals,
      });
      setError("");
    } catch (e) {
      setError(apiMessage(e, t));
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load]);
  const rows = useMemo(
    () =>
      data.inventory.filter((x) =>
        JSON.stringify(x).toLowerCase().includes(q.toLowerCase())
      ),
    [data.inventory, q]
  );
  const createLocation = async (event) => {
    event.preventDefault();
    try {
      await api.finishedLocationCreate({
        ...locationForm,
        parent_id: locationForm.parent_id
          ? Number(locationForm.parent_id)
          : null,
      });
      setLocationForm({
        parent_id: "",
        location_type: "warehouse",
        segment_code: "",
        description: "",
      });
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  const place = async (row, locationId) => {
    if (!locationId) return;
    try {
      await api.mesWarehousePlacePackage(
        row.job_id,
        row.package_id || row.id,
        Number(locationId)
      );
      await load();
    } catch (e) {
      setError(apiMessage(e, t));
    }
  };
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-black">
          {t("checkpointD.warehouse.title")}
        </h1>
        <p className="text-sm text-[var(--brand-muted)]">
          {t("checkpointD.warehouse.subtitle")}
        </p>
      </header>
      {error && <ErrorAlert message={error} onRetry={load} />}
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          "waiting_for_placement",
          "placed",
          "assigned_to_shipment",
          "loaded",
        ].map((key) => (
          <div className={panel} key={key}>
            <small>{t(`checkpointD.status.${key}`)}</small>
            <strong className="block text-2xl">
              {number(data.totals[key], locale)}
            </strong>
          </div>
        ))}
      </div>
      <input
        className={field}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t("checkpointD.warehouse.search")}
        aria-label={t("checkpointD.actions.search")}
      />
      {hasPermission("production_projects_package") && (
        <form
          className={`${panel} grid gap-3 md:grid-cols-5`}
          onSubmit={createLocation}
        >
          <select
            className={field}
            value={locationForm.parent_id}
            onChange={(e) =>
              setLocationForm({ ...locationForm, parent_id: e.target.value })
            }
          >
            <option value="">{t("checkpointD.warehouse.root")}</option>
            {data.locations
              .filter((x) => x.is_active)
              .map((x) => (
                <option key={x.id} value={x.id}>
                  {x.code}
                </option>
              ))}
          </select>
          <select
            className={field}
            value={locationForm.location_type}
            onChange={(e) =>
              setLocationForm({
                ...locationForm,
                location_type: e.target.value,
              })
            }
          >
            {["warehouse", "zone", "aisle", "rack", "shelf", "bin"].map((x) => (
              <option key={x} value={x}>
                {t(`checkpointD.location.${x}`)}
              </option>
            ))}
          </select>
          <input
            className={field}
            required
            value={locationForm.segment_code}
            onChange={(e) =>
              setLocationForm({ ...locationForm, segment_code: e.target.value })
            }
            placeholder={t("checkpointD.fields.code")}
          />
          <input
            className={field}
            value={locationForm.description}
            onChange={(e) =>
              setLocationForm({ ...locationForm, description: e.target.value })
            }
            placeholder={t("checkpointD.fields.description")}
          />
          <button className="brand-btn rounded-xl px-4 py-2 font-bold text-white">
            {t("checkpointD.actions.createLocation")}
          </button>
        </form>
      )}
      <div className="overflow-x-auto rounded-2xl border">
        <table className="w-full min-w-[1000px] text-sm">
          <thead>
            <tr>
              {[
                "package",
                "product",
                "project",
                "destination",
                "quantity",
                "location",
                "received",
                "status",
              ].map((key) => (
                <th className="p-3 text-left" key={key}>
                  {t(`checkpointD.fields.${key}`)}
                </th>
              ))}
              <th className="p-3 text-left">{t("traceability.products")}</th>
              <th className="p-3 text-left">{t("checkpointD.fields.logistics")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr className="border-t" key={row.package_id || row.id || index}>
                <td className="p-3 font-mono">
                  {row.label_code || row.qr_code || row.package_number || "—"}
                </td>
                <td className="p-3">
                  {row.product_code || row.template_code || "—"}
                </td>
                <td className="p-3">{row.project_code || "—"}</td>
                <td className="p-3">{row.destination_city || "—"}</td>
                <td className="p-3">{number(row.quantity, locale)}</td>
                <td className="p-3">
                  {row.location_code ||
                    row.location?.code ||
                    (hasPermission("production_projects_package") ? (
                      <select
                        className={field}
                        defaultValue=""
                        onChange={(e) => place(row, e.target.value)}
                      >
                        <option value="">
                          {t("checkpointD.warehouse.selectLocation")}
                        </option>
                        {data.locations
                          .filter(
                            (l) =>
                              l.is_active &&
                              ["shelf", "bin"].includes(l.location_type)
                          )
                          .map((l) => (
                            <option key={l.id} value={l.id}>
                              {l.code}
                            </option>
                          ))}
                      </select>
                    ) : (
                      "—"
                    ))}
                </td>
                <td className="p-3">
                  {date(row.received_at || row.created_at, locale)}
                </td>
                <td className="p-3">
                  {t(
                    `checkpointD.status.${
                      row.status || "waiting_for_placement"
                    }`
                  )}
                </td>
                <td className="p-3">
                  <ProductPassportActions
                    packageId={row.package_id}
                    serials={row.passport_serials || []}
                    compact
                    onMessage={setError}
                  />
                </td>
                <td className="p-3">
                  {row.status === "placed" ? (
                    <Link className="whitespace-nowrap rounded-xl border px-3 py-2 font-bold" to={`/logistics/shipments?placement_id=${row.id}`}>
                      {t("logisticsCenter.readyCargo.openPlanner")}
                    </Link>
                  ) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && (
        <div className={`${panel} text-center`}>
          {t("checkpointD.warehouse.empty")}
        </div>
      )}
    </section>
  );
}
