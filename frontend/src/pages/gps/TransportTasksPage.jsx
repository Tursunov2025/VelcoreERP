import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import BackButton from "../../components/ui/BackButton";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import PageHeader from "../../components/ui/PageHeader";
import { useAuth } from "../../context/AuthContext";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const emptyForm = {
  title: "",
  description: "",
  driver_user_id: "",
  mes_vehicle_id: "",
  origin: "",
  destination: "",
  customer_name: "",
  customer_phone: "",
  cargo_description: "",
  origin_latitude: "",
  origin_longitude: "",
  destination_latitude: "",
  destination_longitude: "",
};

const STATUS_LABELS = {
  assigned: "Yangi",
  picked_up: "Yuk olindi",
  delivered: "Yuk topshirildi",
  completed: "Bajarildi",
  cancelled: "Bekor",
  active: "Faol",
};

export default function TransportTasksPage() {
  const { isAdmin, hasPermission } = useAuth();
  const canManage = isAdmin || hasPermission("export_manage");
  const canView = isAdmin || hasPermission("export_view");

  const [tasks, setTasks] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm });

  const [mapPicker, setMapPicker] = useState(null);
  const [mapPoint, setMapPoint] = useState(null);
  const mapContainerRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (!mapPicker || !mapContainerRef.current) return;

    const rawLat =
      mapPicker === "destination"
        ? form.destination_latitude
        : form.origin_latitude;

    const rawLng =
      mapPicker === "destination"
        ? form.destination_longitude
        : form.origin_longitude;

    const initialLat =
      rawLat !== "" && rawLat !== null && rawLat !== undefined
        ? Number(rawLat)
        : null;

    const initialLng =
      rawLng !== "" && rawLng !== null && rawLng !== undefined
        ? Number(rawLng)
        : null;

    const hasInitialPoint =
      Number.isFinite(initialLat) &&
      Number.isFinite(initialLng) &&
      Math.abs(initialLat) <= 90 &&
      Math.abs(initialLng) <= 180;

    const lat = hasInitialPoint ? initialLat : 41.2995;
    const lng = hasInitialPoint ? initialLng : 69.2401;

    const map = L.map(mapContainerRef.current).setView([lat, lng], 13);

    const markerIcon = L.divIcon({
      className: "velcore-map-marker",
      html: '<div style="width:18px;height:18px;border-radius:50%;background:#e11d48;border:3px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.45);"></div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });

    L.tileLayer(
      import.meta.env.VITE_MAP_TILE_URL ||
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution: "© OpenStreetMap contributors",
      }
    ).addTo(map);

    if (hasInitialPoint) {
      markerRef.current = L.marker(
        [initialLat, initialLng],
        { icon: markerIcon }
      ).addTo(map);

      setMapPoint({
        latitude: initialLat,
        longitude: initialLng,
      });
    } else {
      setMapPoint(null);
    }

    map.on("click", (e) => {
      const point = {
        latitude: e.latlng.lat,
        longitude: e.latlng.lng,
      };

      setMapPoint(point);

      if (markerRef.current) {
        markerRef.current.setLatLng([
          point.latitude,
          point.longitude,
        ]);
      } else {
        markerRef.current = L.marker(
          [point.latitude, point.longitude],
          { icon: markerIcon }
        ).addTo(map);
      }
    });

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      if (markerRef.current) {
        markerRef.current.remove();
        markerRef.current = null;
      }
      map.remove();
    };
  }, [mapPicker]);

  const reverseGeocode = async (latitude, longitude) => {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(
          latitude
        )}&lon=${encodeURIComponent(
          longitude
        )}&zoom=18&addressdetails=1`,
        {
          headers: {
            Accept: "application/json",
            "Accept-Language": "uz,ru,en",
          },
        }
      );

      if (!response.ok) return "";

      const data = await response.json();
      return data.display_name || "";
    } catch {
      return "";
    }
  };

  const openMapPicker = (type) => {
    setMapPoint(null);
    setMapPicker(type);
  };

  const closeMapPicker = () => {
    setMapPicker(null);
    setMapPoint(null);
  };

  const load = useCallback(async () => {
    if (!canView) return;

    setError("");

    try {
      const [taskData, vehicleData, driverData] = await Promise.all([
        api.gpsTransportTasks(),
        api.finishedVehicles(true),
        api.finishedDrivers(true),
      ]);

      setTasks(taskData.tasks || []);
      setVehicles(vehicleData.vehicles || []);
      setDrivers(driverData.drivers || []);
    } catch (e) {
      setError(e.message || "Ma'lumotlarni yuklashda xatolik");
    } finally {
      setLoading(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const createTask = async (e) => {
    e.preventDefault();

    if (!form.title.trim()) return;
    if (!form.driver_user_id) return;
    if (!form.mes_vehicle_id) return;

    try {
      await api.gpsCreateTransportTask({
        title: form.title.trim(),
        description: form.description.trim(),
        driver_user_id: Number(form.driver_user_id),
        mes_vehicle_id: Number(form.mes_vehicle_id),
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        customer_name: form.customer_name.trim(),
        customer_phone: form.customer_phone.trim(),
        cargo_description: form.cargo_description.trim(),
        origin_latitude:
          form.origin_latitude === ""
            ? null
            : Number(form.origin_latitude),
        origin_longitude:
          form.origin_longitude === ""
            ? null
            : Number(form.origin_longitude),
        destination_latitude:
          form.destination_latitude === ""
            ? null
            : Number(form.destination_latitude),
        destination_longitude:
          form.destination_longitude === ""
            ? null
            : Number(form.destination_longitude),
        status: "assigned",
      });

      setForm({ ...emptyForm });
      setShowForm(false);
      load();
    } catch (e) {
      setError(e.message || "Vazifa yaratishda xatolik");
    }
  };

  if (!canView) {
    return (
      <p className="py-12 text-center text-red-500">
        Ruxsat yo&apos;q
      </p>
    );
  }

  return (
    <div className="pb-24">
      <BackButton
        fallback="/gps"
        label="GPS Monitoring"
        className="mb-4"
      />

      <PageHeader
        title="Haydovchi vazifalari"
        subtitle="Haydovchiga yuk topshirig'i berish va bajarilishini kuzatish"
        actions={
          canManage ? (
            <button
              type="button"
              onClick={() => setShowForm((v) => !v)}
              className="rounded-xl px-4 py-2 text-sm font-bold text-white"
              style={{ backgroundColor: "var(--brand-button)" }}
            >
              + Vazifa berish
            </button>
          ) : null
        }
      />

      {loading ? <LoadingSpinner /> : null}

      <ErrorAlert message={error} onRetry={load} />

      {showForm && canManage ? (
        <form
          onSubmit={createTask}
          className="mb-6 space-y-3 rounded-3xl border bg-[var(--brand-card)] p-4"
        >
          <h2 className="text-lg font-black">Yangi haydovchi vazifasi</h2>

          <input
            value={form.title}
            onChange={(e) =>
              setForm((f) => ({ ...f, title: e.target.value }))
            }
            placeholder="Vazifa nomi *"
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
            required
          />

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <input
                value={form.origin}
                onChange={(e) =>
                  setForm((f) => ({ ...f, origin: e.target.value }))
                }
                placeholder="Qayerdan"
                className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
              />
              <button
                type="button"
                onClick={() => openMapPicker("origin")}
                className="w-full rounded-xl border px-3 py-2 text-sm font-bold"
              >
                🗺 Kartadan tanlash
              </button>
            </div>

            <div className="space-y-2">
              <input
                value={form.destination}
                onChange={(e) =>
                  setForm((f) => ({ ...f, destination: e.target.value }))
                }
                placeholder="Qayerga *"
                className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
                required
              />
              <button
                type="button"
                onClick={() => openMapPicker("destination")}
                className="w-full rounded-xl border px-3 py-2 text-sm font-bold"
              >
                🗺 Kartadan tanlash
              </button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={form.driver_user_id}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  driver_user_id: e.target.value,
                }))
              }
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
              required
            >
              <option value="">Haydovchini tanlang *</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name || d.username}
                </option>
              ))}
            </select>

            <select
              value={form.mes_vehicle_id}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  mes_vehicle_id: e.target.value,
                }))
              }
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
              required
            >
              <option value="">Mashinani tanlang *</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate_number || v.registration_number || v.name || `ID ${v.id}`}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={form.customer_name}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  customer_name: e.target.value,
                }))
              }
              placeholder="Mijoz nomi"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />

            <input
              value={form.customer_phone}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  customer_phone: e.target.value,
                }))
              }
              placeholder="Mijoz telefoni"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />
          </div>

          <textarea
            value={form.cargo_description}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                cargo_description: e.target.value,
              }))
            }
            placeholder="Yuk tavsifi"
            rows={3}
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
          />

          <textarea
            value={form.description}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                description: e.target.value,
              }))
            }
            placeholder="Qo'shimcha izoh"
            rows={2}
            className="w-full rounded-xl border bg-transparent px-3 py-3 text-sm"
          />

          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={form.destination_latitude}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  destination_latitude: e.target.value,
                }))
              }
              placeholder="Latitude (ixtiyoriy)"
              inputMode="decimal"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />

            <input
              value={form.destination_longitude}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  destination_longitude: e.target.value,
                }))
              }
              placeholder="Longitude (ixtiyoriy)"
              inputMode="decimal"
              className="rounded-xl border bg-transparent px-3 py-3 text-sm"
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-xl py-3 font-bold text-white"
            style={{ backgroundColor: "var(--brand-button)" }}
          >
            Haydovchiga vazifa berish
          </button>
        </form>
      ) : null}

      {mapPicker ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
          <div className="flex w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-[var(--brand-card)] shadow-2xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div>
                <p className="font-black">
                  {mapPicker === "destination"
                    ? "Qayerga — xaritadan tanlang"
                    : "Qayerdan — xaritadan tanlang"}
                </p>

                <p className="text-xs text-[var(--brand-muted)]">
                  {mapPoint
                    ? `${mapPoint.latitude.toFixed(6)}, ${mapPoint.longitude.toFixed(6)}`
                    : "Xaritadagi nuqtani bosing"}
                </p>
              </div>

              <button
                type="button"
                onClick={closeMapPicker}
                className="rounded-lg border px-3 py-2"
              >
                ✕
              </button>
            </div>

            <div
              ref={mapContainerRef}
              className="h-[60vh] min-h-[360px] w-full"
            />

            <div className="flex justify-end gap-2 border-t p-4">
              <button
                type="button"
                onClick={closeMapPicker}
                className="rounded-xl border px-4 py-2"
              >
                Bekor qilish
              </button>

              <button
                type="button"
                disabled={!mapPoint}
                onClick={async () => {
                  if (!mapPoint) return;

                  const address = await reverseGeocode(
                    mapPoint.latitude,
                    mapPoint.longitude
                  );

                  setForm((f) => {
                    if (mapPicker === "destination") {
                      return {
                        ...f,
                        destination:
                          address || f.destination,
                        destination_latitude:
                          String(mapPoint.latitude.toFixed(6)),
                        destination_longitude:
                          String(mapPoint.longitude.toFixed(6)),
                      };
                    }

                    return {
                      ...f,
                      origin:
                        address ||
                        `${mapPoint.latitude.toFixed(6)}, ${mapPoint.longitude.toFixed(6)}`,
                      origin_latitude:
                        String(mapPoint.latitude.toFixed(6)),
                      origin_longitude:
                        String(mapPoint.longitude.toFixed(6)),
                    };
                  });

                  closeMapPicker();
                }}
                className="rounded-xl px-4 py-2 font-bold text-white disabled:opacity-50"
                style={{ backgroundColor: "var(--brand-button)" }}
              >
                📍 Nuqtani tanlash
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        {tasks.map((task) => (
          <div
            key={task.id}
            className="rounded-2xl border bg-[var(--brand-card)] p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-bold text-[var(--brand-text)]">
                  {task.title}
                </p>

                <p className="text-sm text-[var(--brand-muted)]">
                  {task.driver_name || task.driver_full_name || "Haydovchi —"}
                  {" · "}
                  {task.vehicle_plate || task.mes_vehicle_plate || "Mashina —"}
                </p>

                <p className="text-xs text-[var(--brand-muted)]">
                  {task.origin || "—"} → {task.destination || "—"}
                </p>
              </div>

              <span className="rounded-full bg-blue-100 px-3 py-1 text-[10px] font-bold text-blue-700">
                {STATUS_LABELS[task.status] || task.status}
              </span>
            </div>

            {task.cargo_description ? (
              <p className="mt-3 text-sm">
                <b>Yuk:</b> {task.cargo_description}
              </p>
            ) : null}

            {task.customer_name || task.customer_phone ? (
              <p className="mt-1 text-sm text-[var(--brand-muted)]">
                <b>Mijoz:</b>{" "}
                {task.customer_name || "—"}
                {task.customer_phone
                  ? ` · ${task.customer_phone}`
                  : ""}
              </p>
            ) : null}

            {task.picked_up_at ? (
              <p className="mt-2 text-xs text-[var(--brand-muted)]">
                Yuk olindi: {new Date(task.picked_up_at).toLocaleString()}
              </p>
            ) : null}

            {task.delivered_at ? (
              <p className="text-xs text-[var(--brand-muted)]">
                Yuk topshirildi: {new Date(task.delivered_at).toLocaleString()}
              </p>
            ) : null}

            {task.completed_at ? (
              <p className="text-xs text-green-600">
                Bajarildi: {new Date(task.completed_at).toLocaleString()}
              </p>
            ) : null}

            {task.completion_photo_url ? (
              <a
                href={task.completion_photo_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block text-sm font-bold text-blue-600"
              >
                📷 Yakuniy rasm
              </a>
            ) : null}

            {task.latest_location?.online ? (
              <p className="mt-2 text-xs text-green-600">
                GPS online ·{" "}
                {Math.round(task.latest_location.speed ?? 0)} km/h
              </p>
            ) : null}
          </div>
        ))}

        {!loading && tasks.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--brand-muted)]">
            Hozircha haydovchi vazifalari yo&apos;q.
          </p>
        ) : null}
      </div>
    </div>
  );
}
