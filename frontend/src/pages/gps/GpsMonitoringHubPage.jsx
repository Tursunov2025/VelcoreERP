import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ui/ErrorAlert";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import FleetMap from "../../components/gps/FleetMap";

const STATUS = {
  moving: {
    uz: "Harakatda",
    ru: "В движении",
    color: "#16a34a",
    icon: "🟢",
  },
  stopped: {
    uz: "To‘xtagan",
    ru: "Стоит",
    color: "#eab308",
    icon: "🟡",
  },
  stale: {
    uz: "Aloqa sust",
    ru: "Связь устарела",
    color: "#f97316",
    icon: "🟠",
  },
  no_signal: {
    uz: "Signal yo‘q",
    ru: "Нет сигнала",
    color: "#64748b",
    icon: "⚫",
  },
  unbound: {
    uz: "Qurilma ulanmagan",
    ru: "Устройство не привязано",
    color: "#64748b",
    icon: "⚪",
  },
};

const UI = {
  uz: {
    title: "GPS Monitoring",
    subtitle: "Transport vositalarini real vaqt rejimida kuzatish",
    all: "Barchasi",
    moving: "Harakatda",
    stopped: "To‘xtagan",
    offline: "Aloqa yo‘q",
    search: "Mashina qidirish...",
    vehicles: "Mashinalar",
    total: "Jami",
    today: "Bugun",
    week: "Hafta",
    totalDistance: "Umumiy",
    speed: "Tezlik",
    driver: "Haydovchi",
    phone: "Telefon",
    lastSignal: "Oxirgi signal",
    status: "Holat",
    trip: "Safar",
    destination: "Manzil",
    coordinates: "Koordinatalar",
    device: "GPS qurilma",
    history: "Marshrut",
    daily: "Kunlik",
    stops: "To‘xtashlar",
    noData: "Ma’lumot yo‘q",
    loading: "Yuklanmoqda...",
    minutes: "daqiqa",
    hours: "soat",
    min: "min",
    km: "km",
    updated: "Yangilangan",
    selected: "Tanlangan transport",
    close: "Yopish",
    todayDistance: "Bugungi masofa",
    weekDistance: "Haftalik masofa",
    totalDistanceLabel: "Jami masofa",
    stopLocation: "To‘xtagan joy",
    stoppedFor: "To‘xtagan vaqt",
    start: "Boshlanish",
    end: "Tugash",
    duration: "Davomiyligi",
    noStops: "To‘xtashlar topilmadi",
    noHistory: "Tarix mavjud emas",
    refresh: "Yangilash",
    allStatuses: "Barcha holatlar",
    currentStop: "Hozirgi to‘xtash",
    stoppedSince: "To‘xtaganidan beri",
    pointCount: "GPS nuqtalari",
  },
  ru: {
    title: "GPS Мониторинг",
    subtitle: "Мониторинг транспорта в реальном времени",
    all: "Все",
    moving: "В движении",
    stopped: "Стоит",
    offline: "Нет связи",
    search: "Поиск автомобиля...",
    vehicles: "Автомобили",
    total: "Всего",
    today: "Сегодня",
    week: "Неделя",
    totalDistance: "Общее",
    speed: "Скорость",
    driver: "Водитель",
    phone: "Телефон",
    lastSignal: "Последний сигнал",
    status: "Статус",
    trip: "Рейс",
    destination: "Назначение",
    coordinates: "Координаты",
    device: "GPS устройство",
    history: "Маршрут",
    daily: "По дням",
    stops: "Остановки",
    noData: "Нет данных",
    loading: "Загрузка...",
    minutes: "минут",
    hours: "часов",
    min: "мин",
    km: "км",
    updated: "Обновлено",
    selected: "Выбранный транспорт",
    close: "Закрыть",
    todayDistance: "Расстояние сегодня",
    weekDistance: "Расстояние за неделю",
    totalDistanceLabel: "Общее расстояние",
    stopLocation: "Место остановки",
    stoppedFor: "Время остановки",
    start: "Начало",
    end: "Конец",
    duration: "Продолжительность",
    noStops: "Остановки не найдены",
    noHistory: "История отсутствует",
    refresh: "Обновить",
    allStatuses: "Все статусы",
    currentStop: "Текущая остановка",
    stoppedSince: "Стоит с",
    pointCount: "GPS точек",
  },
};

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  }).format(Number(value || 0));
}

function formatDateTime(value, lang = "uz") {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleString(lang === "ru" ? "ru-RU" : "uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(seconds, lang) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "—";

  const total = Math.max(0, Math.floor(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);

  if (hours > 0) {
    return `${hours} ${UI[lang].hours} ${minutes} ${UI[lang].minutes}`;
  }

  return `${minutes} ${UI[lang].minutes}`;
}

function getStatus(vehicle) {
  return STATUS[vehicle?.status] || STATUS.no_signal;
}

function StatCard({ title, value, subtitle, accent }) {
  return (
    <div
      className="rounded-2xl border bg-[var(--brand-card)] p-4 shadow-sm"
      style={{ borderColor: accent ? `${accent}55` : "var(--brand-border)" }}
    >
      <div className="text-xs font-medium text-[var(--brand-muted)]">{title}</div>
      <div
        className="mt-1 text-2xl font-black"
        style={{ color: accent || "var(--brand-primary)" }}
      >
        {value}
      </div>
      {subtitle ? (
        <div className="mt-1 text-xs text-[var(--brand-muted)]">{subtitle}</div>
      ) : null}
    </div>
  );
}

function StatusBadge({ vehicle, lang }) {
  const status = getStatus(vehicle);
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold"
      style={{
        color: status.color,
        backgroundColor: `${status.color}18`,
      }}
    >
      {status.icon} {status[lang]}
    </span>
  );
}

function VehicleRow({ vehicle, selected, onClick, lang }) {
  const status = getStatus(vehicle);

  return (
    <button
      type="button"
      onClick={() => onClick(vehicle.vehicle_id)}
      className="w-full rounded-xl border p-3 text-left transition"
      style={{
        borderColor: selected ? status.color : "var(--brand-border)",
        background: selected
          ? `${status.color}0d`
          : "var(--brand-card)",
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-black">
            {vehicle.registration_number || `#${vehicle.vehicle_id}`}
          </div>
          <div className="truncate text-xs text-[var(--brand-muted)]">
            {vehicle.vehicle_model || vehicle.vehicle_type || "—"}
          </div>
        </div>

        <span
          className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: status.color }}
        />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-black/[0.03] p-1.5 dark:bg-white/[0.04]">
          <div className="text-xs font-bold">
            {formatNumber(vehicle.daily_distance_km)}
          </div>
          <div className="text-[10px] text-[var(--brand-muted)]">km/{lang === "ru" ? "day" : "kun"}</div>
        </div>

        <div className="rounded-lg bg-black/[0.03] p-1.5 dark:bg-white/[0.04]">
          <div className="text-xs font-bold">
            {formatNumber(vehicle.weekly_distance_km)}
          </div>
          <div className="text-[10px] text-[var(--brand-muted)]">km/{lang === "ru" ? "week" : "hafta"}</div>
        </div>

        <div className="rounded-lg bg-black/[0.03] p-1.5 dark:bg-white/[0.04]">
          <div className="text-xs font-bold">
            {formatNumber(vehicle.latest?.speed_kmh)}
          </div>
          <div className="text-[10px] text-[var(--brand-muted)]">km/h</div>
        </div>
      </div>
    </button>
  );
}

function DetailMetric({ label, value, icon }) {
  return (
    <div className="rounded-xl border border-[var(--brand-border)] bg-black/[0.02] p-3 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-xs text-[var(--brand-muted)]">
        {icon ? <span>{icon}</span> : null}
        <span>{label}</span>
      </div>
      <div className="mt-1 break-words text-sm font-black">{value || "—"}</div>
    </div>
  );
}

function StopList({ stops, lang, onSelectStop }) {
  if (!stops?.length) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--brand-border)] p-6 text-center text-sm text-[var(--brand-muted)]">
        {UI[lang].noStops}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {stops.map((stop, index) => {
        const startAt = stop.start_at || stop.started_at;
        const endAt = stop.end_at || stop.ended_at;

        const address =
          stop.address ||
          [stop.city, stop.state, stop.country]
            .filter(Boolean)
            .join(", ") ||
          "—";

        const latitude =
          stop.latitude != null
            ? Number(stop.latitude).toFixed(6)
            : "—";

        const longitude =
          stop.longitude != null
            ? Number(stop.longitude).toFixed(6)
            : "—";

        return (
          <div
            key={`${startAt || index}-${index}`}
            className="rounded-xl border border-[var(--brand-border)] bg-[var(--brand-card)] p-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-yellow-500/15 text-xs font-black text-yellow-700 dark:text-yellow-300">
                    {index + 1}
                  </span>

                  <div className="truncate font-black">
                    {address}
                  </div>
                </div>

                <div className="mt-1 text-[11px] text-[var(--brand-muted)]">
                  {latitude}, {longitude}
                </div>

              {stop.latitude != null && stop.longitude != null ? (
                <button
                  type="button"
                  onClick={() =>
                    onSelectStop?.({
                      latitude: Number(stop.latitude),
                      longitude: Number(stop.longitude),
                      address,
                      startAt,
                      endAt,
                      duration_seconds: stop.duration_seconds,
                    })
                  }
                  className="mt-2 rounded-lg border border-[var(--brand-border)] px-2 py-1 text-[11px] font-black text-[var(--brand)] hover:bg-black/[0.04] dark:hover:bg-white/[0.05]"
                >
                  📍 Xaritada
                </button>
              ) : null}
              </div>

              <span className="shrink-0 rounded-full bg-yellow-500/10 px-2 py-1 text-xs font-black text-yellow-700 dark:text-yellow-300">
                {formatDuration(stop.duration_seconds, lang)}
              </span>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg bg-black/[0.03] p-2 dark:bg-white/[0.04]">
                <div className="text-[10px] text-[var(--brand-muted)]">
                  {UI[lang].start}
                </div>
                <div className="mt-0.5 font-bold">
                  {formatDateTime(startAt, lang)}
                </div>
              </div>

              <div className="rounded-lg bg-black/[0.03] p-2 dark:bg-white/[0.04]">
                <div className="text-[10px] text-[var(--brand-muted)]">
                  {UI[lang].end}
                </div>
                <div className="mt-0.5 font-bold">
                  {formatDateTime(endAt, lang)}
                </div>
              </div>
            </div>

            {stop.point_count != null ? (
              <div className="mt-2 text-[11px] text-[var(--brand-muted)]">
                📍 {UI[lang].pointCount || "GPS nuqtalari"}:{" "}
                <strong>{stop.point_count}</strong>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function DailyList({ rows, lang }) {
  if (!rows?.length) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--brand-border)] p-6 text-center text-sm text-[var(--brand-muted)]">
        {UI[lang].noHistory}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div
          key={`${row.date || index}-${index}`}
          className="grid grid-cols-3 gap-3 rounded-xl border border-[var(--brand-border)] p-3"
        >
          <div>
            <div className="text-[10px] text-[var(--brand-muted)]">DATE</div>
            <div className="text-sm font-bold">{row.date || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--brand-muted)]">KM</div>
            <div className="text-sm font-black">
              {formatNumber(row.distance_km)}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--brand-muted)]">
              {UI[lang].stops}
            </div>
            <div className="text-sm font-black">
              {row.stop_count ?? row.stops_count ?? 0}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function GpsMonitoringHubPage() {
  const [lang, setLang] = useState("uz");
  const [fleet, setFleet] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [route, setRoute] = useState([]);
  const [daily, setDaily] = useState([]);
  const [stops, setStops] = useState([]);
  const [mapFocusPoint, setMapFocusPoint] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("history");
  const selectedVehicleIdRef = useRef(null);

  const t = UI[lang];

  const loadFleet = useCallback(async () => {
    try {
      const result = await api.gpsTrackingFleet();
      const items = Array.isArray(result) ? result : result?.items || [];

      setFleet(items);
      setError("");

      // Keep the selected vehicle sticky during live refresh.
      // A temporary omission from one fleet response must never
      // automatically switch the operator to another vehicle.
      if (selectedVehicleIdRef.current == null && items.length > 0) {
        const firstId = items[0].vehicle_id;
        selectedVehicleIdRef.current = firstId;
        setSelectedId(firstId);
      }
    } catch (e) {
      setError(e?.message || "GPS API error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const poll = async () => {
      await loadFleet();

      if (!cancelled) {
        timer = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [loadFleet]);

  useEffect(() => {
    selectedVehicleIdRef.current = selectedId;
  }, [selectedId]);

  const selectedVehicle = useMemo(
    () =>
      fleet.find(
        (item) => Number(item.vehicle_id) === Number(selectedId)
      ) || null,
    [fleet, selectedId]
  );

  const currentStop = useMemo(() => {
    if (
      !selectedVehicle ||
      selectedVehicle.status !== "stopped" ||
      !stops?.length
    ) {
      return null;
    }

    const sorted = [...stops].sort((a, b) => {
      const aTime = new Date(
        a.start_at || a.started_at || 0
      ).getTime();

      const bTime = new Date(
        b.start_at || b.started_at || 0
      ).getTime();

      return bTime - aTime;
    });

    return sorted[0] || null;
  }, [selectedVehicle, stops]);

  const filteredFleet = useMemo(() => {
    const query = search.trim().toLowerCase();

    return fleet.filter((vehicle) => {
      const matchesFilter =
        filter === "all" ||
        (filter === "offline"
          ? ["stale", "no_signal", "unbound"].includes(vehicle.status)
          : vehicle.status === filter);

      const haystack = [
        vehicle.registration_number,
        vehicle.vehicle_model,
        vehicle.vehicle_type,
        vehicle.driver_name,
        vehicle.device_identifier,
        vehicle.trip_number,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return matchesFilter && (!query || haystack.includes(query));
    });
  }, [fleet, search, filter]);

  const stats = useMemo(() => {
    const moving = fleet.filter((x) => x.status === "moving").length;
    const stopped = fleet.filter((x) => x.status === "stopped").length;
    const offline = fleet.filter((x) =>
      ["stale", "no_signal", "unbound"].includes(x.status)
    ).length;

    return {
      total: fleet.length,
      moving,
      stopped,
      offline,
      today: fleet.reduce(
        (sum, x) => sum + Number(x.daily_distance_km || 0),
        0
      ),
      week: fleet.reduce(
        (sum, x) => sum + Number(x.weekly_distance_km || 0),
        0
      ),
    };
  }, [fleet]);

  const loadVehicleHistory = useCallback(async () => {
    if (!selectedId) return;

    setHistoryLoading(true);

    try {
      const vehicleId = selectedId;
      const now = new Date();
      const from = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      const [historyResult, stopsResult] = await Promise.allSettled([
        api.gpsTrackingHistory(
          vehicleId,
          from.toISOString(),
          now.toISOString()
        ),
        api.gpsTrackingHistoryStops(
          vehicleId,
          from.toISOString(),
          now.toISOString()
        ),
      ]);

      if (selectedVehicleIdRef.current !== vehicleId) {
        return;
      }

      if (historyResult.status === "fulfilled") {
        setRoute(
          historyResult.value?.route ||
            historyResult.value?.route_points ||
            []
        );
      } else {
        setRoute([]);
      }

      if (stopsResult.status === "fulfilled") {
        setStops(stopsResult.value?.stops || []);
      } else {
        setStops([]);
      }

      if (
        historyResult.status === "rejected" &&
        stopsResult.status === "rejected"
      ) {
        throw historyResult.reason || stopsResult.reason;
      }
    } catch (e) {
      setError(e?.message || "GPS history error");
      setRoute([]);
      setStops([]);
    } finally {
      if (selectedVehicleIdRef.current === selectedId) {
        setHistoryLoading(false);
      }
    }
  }, [selectedId]);

  const loadDaily = useCallback(async () => {
    if (!selectedId) return;

    const vehicleId = selectedId;
    const now = new Date();
    const toDate = now.toISOString().slice(0, 10);
    const fromDate = new Date(
      now.getTime() - 30 * 24 * 60 * 60 * 1000
    )
      .toISOString()
      .slice(0, 10);

    try {
      const result = await api.gpsTrackingHistoryDaily(
        vehicleId,
        fromDate,
        toDate
      );

      setDaily(result?.items || result?.days || result || []);
    } catch (e) {
      setError(e?.message || "Daily GPS history error");
      setDaily([]);
    }
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;

    loadVehicleHistory();
    loadDaily();
  }, [selectedId, loadVehicleHistory, loadDaily]);

  const selectVehicle = (id) => {
    selectedVehicleIdRef.current = id;
    setSelectedId(id);

    // Old vehicle history must never remain visible
    // while the newly selected vehicle data is loading.
    setRoute([]);
    setStops([]);
    setDaily([]);
    setHistoryLoading(true);
    setTab("history");
  };

  const markerLabels = useMemo(
    () => ({
      driver: t.driver,
      speed: t.speed,
      trip: t.trip,
      lastSignal: t.lastSignal,
      status: t.status,
    }),
    [t]
  );

  const status = selectedVehicle ? getStatus(selectedVehicle) : null;

  return (
    <div className="min-h-screen pb-24">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight sm:text-3xl">
            {t.title}
          </h1>
          <p className="mt-1 text-sm text-[var(--brand-muted)]">
            {t.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-[var(--brand-border)] bg-[var(--brand-card)] p-1">
            <button
              type="button"
              onClick={() => setLang("uz")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                lang === "uz"
                  ? "bg-[var(--brand-primary)] text-white"
                  : ""
              }`}
            >
              🇺🇿 UZ
            </button>

            <button
              type="button"
              onClick={() => setLang("ru")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                lang === "ru"
                  ? "bg-[var(--brand-primary)] text-white"
                  : ""
              }`}
            >
              🇷🇺 RU
            </button>
          </div>

          <button
            type="button"
            onClick={loadFleet}
            className="rounded-xl border border-[var(--brand-border)] bg-[var(--brand-card)] px-4 py-2 text-sm font-bold"
          >
            ↻ {t.refresh}
          </button>
        </div>
      </div>

      <ErrorAlert message={error} onRetry={loadFleet} />

      {loading ? <LoadingSpinner /> : null}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard title={t.total} value={stats.total} />
        <StatCard title={t.moving} value={stats.moving} accent="#16a34a" />
        <StatCard title={t.stopped} value={stats.stopped} accent="#eab308" />
        <StatCard title={t.offline} value={stats.offline} accent="#64748b" />
        <StatCard
          title={t.today}
          value={`${formatNumber(stats.today)} km`}
          accent="#2563eb"
        />
        <StatCard
          title={t.week}
          value={`${formatNumber(stats.week)} km`}
          accent="#7c3aed"
        />
      </div>

      <div className="grid min-h-[700px] gap-4 xl:grid-cols-[300px_minmax(0,1fr)_350px]">
        <aside className="flex min-h-[650px] flex-col rounded-2xl border border-[var(--brand-border)] bg-[var(--brand-card)] p-3">
          <div className="mb-3">
            <div className="mb-2 text-sm font-black">{t.vehicles}</div>

            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.search}
              className="w-full rounded-xl border border-[var(--brand-border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)]"
            />
          </div>

          <div className="mb-3 flex gap-1 overflow-x-auto pb-1">
            {[
              ["all", t.all],
              ["moving", t.moving],
              ["stopped", t.stopped],
              ["offline", t.offline],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-bold ${
                  filter === value
                    ? "bg-[var(--brand-primary)] text-white"
                    : "bg-black/[0.04] dark:bg-white/[0.05]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {filteredFleet.length ? (
              filteredFleet.map((vehicle) => (
                <VehicleRow
                  key={vehicle.vehicle_id}
                  vehicle={vehicle}
                  selected={
                    Number(selectedId) === Number(vehicle.vehicle_id)
                  }
                  onClick={selectVehicle}
                  lang={lang}
                />
              ))
            ) : (
              <div className="p-6 text-center text-sm text-[var(--brand-muted)]">
                {t.noData}
              </div>
            )}
          </div>
        </aside>

        <main className="min-h-[650px] overflow-hidden rounded-2xl border border-[var(--brand-border)] bg-[var(--brand-card)]">
          <div className="flex items-center justify-between border-b border-[var(--brand-border)] px-4 py-3">
            <div>
              <div className="text-sm font-black">
                {selectedVehicle?.registration_number || t.title}
              </div>

              {selectedVehicle ? (
                <div className="mt-1">
                  <StatusBadge vehicle={selectedVehicle} lang={lang} />
                </div>
              ) : null}
            </div>

            {selectedVehicle?.latest ? (
              <div className="text-right">
                <div className="text-lg font-black">
                  {formatNumber(selectedVehicle.latest.speed_kmh)} km/h
                </div>
                <div className="text-xs text-[var(--brand-muted)]">
                  {t.updated}:{" "}
                  {formatDateTime(
                    selectedVehicle.last_signal_at ||
                      selectedVehicle.latest.captured_at,
                    lang
                  )}
                </div>
              </div>
            ) : null}
          </div>

          <FleetMap
            markers={fleet}
            route={route}
            selectedVehicleId={selectedId}
            focusPoint={mapFocusPoint}
            onSelect={selectVehicle}
            labels={markerLabels}
            height="calc(100vh - 270px)"
          />
        </main>

        <aside className="min-h-[650px] rounded-2xl border border-[var(--brand-border)] bg-[var(--brand-card)] p-4">
          {selectedVehicle ? (
            <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xl font-black">
                    {selectedVehicle.registration_number}
                  </div>
                  <div className="mt-1 text-xs text-[var(--brand-muted)]">
                    {selectedVehicle.vehicle_model ||
                      selectedVehicle.vehicle_type ||
                      "—"}
                  </div>
                </div>

                <StatusBadge vehicle={selectedVehicle} lang={lang} />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <DetailMetric
                  label={t.todayDistance}
                  value={`${formatNumber(
                    selectedVehicle.daily_distance_km
                  )} km`}
                  icon="📅"
                />

                <DetailMetric
                  label={t.weekDistance}
                  value={`${formatNumber(
                    selectedVehicle.weekly_distance_km
                  )} km`}
                  icon="📊"
                />

                <DetailMetric
                  label={t.totalDistanceLabel}
                  value={`${formatNumber(
                    selectedVehicle.total_distance_km
                  )} km`}
                  icon="🛣️"
                />

                <DetailMetric
                  label={t.speed}
                  value={`${formatNumber(
                    selectedVehicle.latest?.speed_kmh
                  )} km/h`}
                  icon="⚡"
                />
              </div>

              <div className="mt-3 grid gap-2">
                <DetailMetric
                  label={t.driver}
                  value={selectedVehicle.driver_name}
                  icon="👤"
                />

                <DetailMetric
                  label={t.phone}
                  value={selectedVehicle.driver_phone}
                  icon="вЋпёЏ"
                />

                <DetailMetric
                  label={t.lastSignal}
                  value={formatDateTime(
                    selectedVehicle.last_signal_at ||
                      selectedVehicle.latest?.captured_at,
                    lang
                  )}
                  icon="📍"
                />

                <DetailMetric
                  label={t.device}
                  value={selectedVehicle.device_identifier}
                  icon="📟"
                />

                <DetailMetric
                  label={t.trip}
                  value={
                    selectedVehicle.trip_number ||
                    selectedVehicle.trip_status
                  }
                  icon="🚚"
                />

                <DetailMetric
                  label={t.destination}
                  value={
                    selectedVehicle.destination_address ||
                    selectedVehicle.destination_city ||
                    selectedVehicle.destination_site
                  }
                  icon="📍"
                />

                <DetailMetric
                  label={t.coordinates}
                  value={
                    selectedVehicle.latest?.latitude != null
                      ? `${Number(
                          selectedVehicle.latest.latitude
                        ).toFixed(6)}, ${Number(
                          selectedVehicle.latest.longitude
                        ).toFixed(6)}`
                      : "—"
                  }
                  icon="🌐"
                />
              </div>

              {selectedVehicle.status === "stopped" ? (
                <div className="mt-3 rounded-2xl border border-yellow-500/30 bg-yellow-500/10 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs font-black uppercase tracking-wide text-yellow-700 dark:text-yellow-300">
                      🛑 {t.currentStop || t.stopped}
                    </div>

                    {currentStop ? (
                      <span className="rounded-full bg-yellow-500/15 px-2 py-1 text-[10px] font-black text-yellow-700 dark:text-yellow-300">
                        {formatDuration(currentStop.duration_seconds, lang)}
                      </span>
                    ) : null}
                  </div>

                  {currentStop ? (
                    <>
                      <div className="mt-3 text-sm font-black">
                        {currentStop.address ||
                          [
                            currentStop.city,
                            currentStop.state,
                            currentStop.country,
                          ]
                            .filter(Boolean)
                            .join(", ") ||
                          "—"}
                      </div>

                      <div className="mt-2 text-[11px] text-[var(--brand-muted)]">
                        📍{" "}
                        {currentStop.latitude != null
                          ? `${Number(currentStop.latitude).toFixed(6)}, ${Number(
                              currentStop.longitude
                            ).toFixed(6)}`
                          : "—"}
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-lg bg-white/50 p-2 dark:bg-black/10">
                          <div className="text-[10px] text-[var(--brand-muted)]">
                            {t.stoppedSince || t.start}
                          </div>
                          <div className="mt-0.5 font-bold">
                            {formatDateTime(
                              currentStop.start_at || currentStop.started_at,
                              lang
                            )}
                          </div>
                        </div>

                        <div className="rounded-lg bg-white/50 p-2 dark:bg-black/10">
                          <div className="text-[10px] text-[var(--brand-muted)]">
                            {t.duration}
                          </div>
                          <div className="mt-0.5 font-black">
                            {formatDuration(
                              currentStop.duration_seconds,
                              lang
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="mt-2 text-xs text-[var(--brand-muted)]">
                      {t.noStops}
                    </div>
                  )}
                </div>
              ) : null}

              <div className="mt-4">
                <div className="mb-2 flex gap-1 rounded-xl bg-black/[0.04] p-1 dark:bg-white/[0.04]">
                  {[
                    ["history", t.history],
                    ["daily", t.daily],
                    ["stops", t.stops],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setTab(value)}
                      className={`flex-1 rounded-lg px-2 py-2 text-xs font-bold ${
                        tab === value
                          ? "bg-[var(--brand-card)] shadow-sm"
                          : ""
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {historyLoading ? (
                  <div className="py-6 text-center text-xs text-[var(--brand-muted)]">
                    {t.loading}
                  </div>
                ) : null}

                {!historyLoading && tab === "history" ? (
                  <div className="rounded-xl border border-[var(--brand-border)] p-3 text-xs text-[var(--brand-muted)]">
                    {route.length
                      ? `${route.length} GPS ${lang === "ru" ? "точек маршрута" : "ta marshrut nuqtasi"}`
                      : t.noHistory}
                  </div>
                ) : null}

                {!historyLoading && tab === "daily" ? (
                  <div className="max-h-64 overflow-y-auto">
                    <DailyList rows={daily} lang={lang} />
                  </div>
                ) : null}

                {!historyLoading && tab === "stops" ? (
                  <div className="max-h-[420px] overflow-y-auto pr-1">
                    <StopList
                      stops={stops}
                      lang={lang}
                      onSelectStop={setMapFocusPoint}
                    />
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-[500px] items-center justify-center text-sm text-[var(--brand-muted)]">
              {t.noData}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}







