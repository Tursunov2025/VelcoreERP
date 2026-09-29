import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";


function animateMarker(marker, target, duration = 4500) {
  if (!marker || !Array.isArray(target)) return;

  const targetLat = Number(target[0]);
  const targetLng = Number(target[1]);

  if (!Number.isFinite(targetLat) || !Number.isFinite(targetLng)) return;

  if (marker._velcoreAnimationFrame) {
    cancelAnimationFrame(marker._velcoreAnimationFrame);
    marker._velcoreAnimationFrame = null;
  }

  const start = marker.getLatLng();
  const startLat = Number(start.lat);
  const startLng = Number(start.lng);

  if (
    !Number.isFinite(startLat) ||
    !Number.isFinite(startLng)
  ) {
    marker.setLatLng([targetLat, targetLng]);
    return;
  }

  const distance =
    Math.abs(targetLat - startLat) +
    Math.abs(targetLng - startLng);

  if (distance < 0.000001) {
    marker.setLatLng([targetLat, targetLng]);
    return;
  }

  const startedAt = performance.now();

  const easeInOut = (t) =>
    t < 0.5
      ? 2 * t * t
      : 1 - Math.pow(-2 * t + 2, 2) / 2;

  const step = (now) => {
    const elapsed = now - startedAt;
    const progress = Math.min(elapsed / duration, 1);
    const eased = easeInOut(progress);

    const lat =
      startLat + (targetLat - startLat) * eased;

    const lng =
      startLng + (targetLng - startLng) * eased;

    marker.setLatLng([lat, lng]);

    if (progress < 1) {
      marker._velcoreAnimationFrame =
        requestAnimationFrame(step);
    } else {
      marker._velcoreAnimationFrame = null;
      marker.setLatLng([targetLat, targetLng]);
    }
  };

  marker._velcoreAnimationFrame =
    requestAnimationFrame(step);
}

const TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ||
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const TILE_ATTRIBUTION = "&copy; OpenStreetMap contributors";

const COLORS = {
  moving: "#16a34a",
  stopped: "rgb(234,179,8)",
  waiting: "rgb(37,99,235)",
  stale: "rgb(249,115,22)",
  offline: "rgb(220,38,38)",
  no_signal: "#64748b",
  unbound: "#64748b",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusLabel(status, labels = {}) {
  const map = {
    moving: labels.moving || "Harakatda",
    stopped: labels.stopped || "ToвЂxtagan",
    waiting: labels.waiting || "Kutilmoqda",
    stale: labels.stale || "Aloqa sust",
    offline: labels.offline || "Offline",
    no_signal: labels.noSignal || "Signal yoвЂq",
    unbound: labels.unbound || "Qurilma ulanmagan",
  };

  return map[status] || status || "NomaвЂ™lum";
}

export function formatGpsAge(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "вЂ”";

  const value = Math.max(0, Math.floor(Number(seconds)));

  if (value < 60) return `${value} s`;
  if (value < 3600) return `${Math.floor(value / 60)} min`;

  return `${Math.floor(value / 3600)} soat`;
}

function popupHtml(marker, labels = {}) {
  const latest = marker.latest || {};
  const status = marker.status || "unbound";
  const color = COLORS[status] || COLORS.unbound;

  const registration =
    marker.registration_number ||
    marker.vehicle_internal_code ||
    `Vehicle #${marker.vehicle_id}`;

  const model = marker.vehicle_model || marker.vehicle_type || "вЂ”";
  const driver = marker.driver_name || "вЂ”";
  const speed =
    latest.speed_kmh == null ? "вЂ”" : `${Number(latest.speed_kmh).toFixed(1)} km/h`;

  return `
    <div style="
      min-width:240px;
      font-family:Inter,Arial,sans-serif;
      font-size:13px;
      line-height:1.45;
    ">
      <div style="
        font-size:17px;
        font-weight:800;
        margin-bottom:4px;
      ">
        ${escapeHtml(registration)}
      </div>

      <div style="
        color:#64748b;
        margin-bottom:10px;
      ">
        ${escapeHtml(model)}
      </div>

      <div style="
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:4px 9px;
        border-radius:999px;
        background:${color}18;
        color:${color};
        font-weight:700;
        margin-bottom:10px;
      ">
        <span style="
          width:8px;
          height:8px;
          border-radius:50%;
          background:${color};
          display:inline-block;
        "></span>
        ${escapeHtml(statusLabel(status, labels))}
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px 12px;">
        <div>
          <div style="color:#94a3b8;font-size:11px;">${escapeHtml(
            labels.driver || "Haydovchi"
          )}</div>
          <div style="font-weight:600;">${escapeHtml(driver)}</div>
        </div>

        <div>
          <div style="color:#94a3b8;font-size:11px;">${escapeHtml(
            labels.speed || "Tezlik"
          )}</div>
          <div style="font-weight:600;">${escapeHtml(speed)}</div>
        </div>
      </div>
    </div>
  `;
}

function markerIcon(marker) {
  const status = marker.status || "unbound";
  const color = COLORS[status] || COLORS.unbound;

  const registration =
    marker.registration_number ||
    marker.vehicle_internal_code ||
    `#${marker.vehicle_id}`;

  const speed =
    marker.latest?.speed_kmh != null
      ? `${Number(marker.latest.speed_kmh).toFixed(0)} km/h`
      : "";

  return L.divIcon({
    className: "velcore-gps-marker",
    html: `
      <div style="
        position:relative;
        display:flex;
        flex-direction:column;
        align-items:center;
        pointer-events:auto;
      ">

        <div style="
          position:absolute;
          bottom:25px;
          left:50%;
          transform:translateX(-50%);
          white-space:nowrap;
          background:#ffffff;
          color:#0f172a;
          border:1px solid ${color};
          border-radius:7px;
          padding:3px 7px;
          font-family:Inter,Arial,sans-serif;
          font-size:12px;
          font-weight:800;
          line-height:1.2;
          box-shadow:0 2px 8px rgba(15,23,42,.20);
          z-index:1000;
        ">
          ${escapeHtml(registration)}
          ${
            speed
              ? `<span style="
                  display:block;
                  font-size:10px;
                  font-weight:600;
                  color:#64748b;
                  text-align:center;
                  margin-top:1px;
                ">${escapeHtml(speed)}</span>`
              : ""
          }
        </div>

        <div style="
          width:18px;
          height:18px;
          border-radius:50%;
          background:${color};
          border:3px solid #ffffff;
          box-shadow:
            0 0 0 2px ${color}55,
            0 3px 8px rgba(0,0,0,.30);
          position:relative;
          z-index:1001;
        "></div>

        <div style="
          width:0;
          height:0;
          border-left:5px solid transparent;
          border-right:5px solid transparent;
          border-top:8px solid ${color};
          margin-top:-2px;
        "></div>
      </div>
    `,
    iconSize: [180, 55],
    iconAnchor: [90, 35],
    popupAnchor: [0, -35],
  });
}

export default function FleetMap({
  markers = [],
  route = [],
  selectedVehicleId,
  focusPoint = null,
  onSelect,
  labels = {},
  height = "520px",
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerLayerRef = useRef(null);
  const routeLayerRef = useRef(null);
  const markerRefs = useRef(new Map());
  const lastFocusPointRef = useRef(null);
  const lastCenteredVehicleRef = useRef(null);
  const initializedViewRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
    }).setView([40.3864, 71.7869], 11);

    L.tileLayer(TILE_URL, {
      attribution: TILE_ATTRIBUTION,
      maxZoom: 19,
    }).addTo(map);

    markerLayerRef.current = L.layerGroup().addTo(map);
    routeLayerRef.current = L.layerGroup().addTo(map);

    mapRef.current = map;

    setTimeout(() => {
      map.invalidateSize();
    }, 100);

    return () => {
      map.remove();
      markerRefs.current.clear();
      mapRef.current = null;
      markerLayerRef.current = null;
      routeLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const markerLayer = markerLayerRef.current;
    const routeLayer = routeLayerRef.current;

    if (!map || !markerLayer || !routeLayer) return;

    const validMarkers = markers.filter(
      (item) =>
        item?.latest &&
        Number.isFinite(Number(item.latest.latitude)) &&
        Number.isFinite(Number(item.latest.longitude))
    );

    const activeIds = new Set();

    validMarkers.forEach((item) => {
      const vehicleId = String(item.vehicle_id);
      const lat = Number(item.latest.latitude);
      const lng = Number(item.latest.longitude);
      const selected =
        vehicleId === String(selectedVehicleId);

      let leafletMarker = markerRefs.current.get(vehicleId);

      if (!leafletMarker) {
        leafletMarker = L.marker([lat, lng], {
          icon: markerIcon(item),
          zIndexOffset: selected ? 10000 : 1000,
        });

        leafletMarker.on("click", () => {
          if (onSelect) onSelect(item);
        });

        leafletMarker.addTo(markerLayer);
        markerRefs.current.set(vehicleId, leafletMarker);
      } else {
        animateMarker(leafletMarker, [lat, lng], 4500);
        leafletMarker.setIcon(markerIcon(item));
        leafletMarker.setZIndexOffset(selected ? 10000 : 1000);
      }

      leafletMarker.bindPopup(popupHtml(item, labels), {
        maxWidth: 320,
        closeButton: true,
      });

      if (selected && !leafletMarker.isPopupOpen()) {
        leafletMarker.openPopup();
      }

      activeIds.add(vehicleId);
    });

    // Remove markers for vehicles that disappeared from the fleet response.
    markerRefs.current.forEach((leafletMarker, vehicleId) => {
      if (!activeIds.has(vehicleId)) {
        if (leafletMarker._velcoreAnimationFrame) {
          cancelAnimationFrame(leafletMarker._velcoreAnimationFrame);
          leafletMarker._velcoreAnimationFrame = null;
        }
        markerLayer.removeLayer(leafletMarker);
        markerRefs.current.delete(vehicleId);
      }
    });

    routeLayer.clearLayers();

    const bounds = validMarkers.map((item) => [
      Number(item.latest.latitude),
      Number(item.latest.longitude),
    ]);

    const validRoute = route
      .map((point) => [
        Number(point.latitude ?? point.lat),
        Number(point.longitude ?? point.lng ?? point.lon),
      ])
      .filter(
        ([lat, lng]) =>
          Number.isFinite(lat) && Number.isFinite(lng)
      );

    if (validRoute.length >= 2) {
      L.polyline(validRoute, {
        color: "rgb(37,99,235)",
        weight: 5,
        opacity: 0.75,
        lineJoin: "round",
      }).addTo(routeLayer);

      validRoute.forEach((point) => bounds.push(point));
    }

    const selected = selectedVehicleId
      ? validMarkers.find(
          (item) =>
            String(item.vehicle_id) === String(selectedVehicleId)
        )
      : null;

    // Do not recenter on live refresh.
    if (
      selected &&
      String(lastCenteredVehicleRef.current) !==
        String(selectedVehicleId)
    ) {
      map.setView(
        [
          Number(selected.latest.latitude),
          Number(selected.latest.longitude),
        ],
        Math.max(map.getZoom(), 14),
        { animate: true }
      );

      lastCenteredVehicleRef.current = selectedVehicleId;
      initializedViewRef.current = true;
      return;
    }

    if (!initializedViewRef.current && !selectedVehicleId) {
      if (bounds.length === 1) {
        map.setView(bounds[0], 13);
        initializedViewRef.current = true;
      } else if (bounds.length > 1) {
        map.fitBounds(bounds, {
          padding: [40, 40],
          maxZoom: 14,
        });
        initializedViewRef.current = true;
      }
    }
    if (
      focusPoint &&
      Number.isFinite(Number(focusPoint.latitude)) &&
      Number.isFinite(Number(focusPoint.longitude))
    ) {
      const focusKey =
        `${Number(focusPoint.latitude).toFixed(6)}:${Number(focusPoint.longitude).toFixed(6)}`;

      if (lastFocusPointRef.current !== focusKey) {
        map.flyTo(
          [
            Number(focusPoint.latitude),
            Number(focusPoint.longitude),
          ],
          Math.max(map.getZoom(), 16),
          {
            animate: true,
            duration: 0.8,
          }
        );

        lastFocusPointRef.current = focusKey;
      }
    }
  }, [markers, route, selectedVehicleId, focusPoint, onSelect, labels]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height,
        minHeight: "420px",
        borderRadius: "14px",
        overflow: "hidden",
        background: "#e2e8f0",
      }}
    />
  );
}





