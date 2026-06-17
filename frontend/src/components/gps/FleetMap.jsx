import { useEffect, useRef } from "react";

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

let leafletPromise = null;

function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) {
    leafletPromise = new Promise((resolve, reject) => {
      if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = LEAFLET_CSS;
        document.head.appendChild(link);
      }
      const script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.onload = () => resolve(window.L);
      script.onerror = reject;
      document.body.appendChild(script);
    });
  }
  return leafletPromise;
}

export function formatGpsAge(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function popupHtml(m) {
  const status = m.online ? (m.moving ? "Moving" : "Online") : "Offline";
  const battery =
    m.battery_level != null ? `${Math.round(m.battery_level)}%` : "—";
  return (
    `<strong>${m.plate_number || "Vehicle"}</strong><br/>` +
    `${m.driver_name || "—"}<br/>` +
    `Speed: ${Math.round(m.speed ?? 0)} km/h<br/>` +
    `Battery: ${battery}<br/>` +
    `Status: ${status}<br/>` +
    `Updated: ${formatGpsAge(m.seconds_since_update)}`
  );
}

/**
 * OpenStreetMap fleet map — markers update in place (no full map rebuild).
 */
export default function FleetMap({ markers = [], route = [], height = "420px", className = "" }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerLayerRef = useRef(new Map());
  const polylineRef = useRef(null);
  const readyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    loadLeaflet()
      .then((L) => {
        if (cancelled || !containerRef.current || mapRef.current) return;

        const map = L.map(containerRef.current).setView([41.2995, 69.2401], 6);
        mapRef.current = map;
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap",
          maxZoom: 19,
        }).addTo(map);
        readyRef.current = true;
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        markerLayerRef.current.clear();
        polylineRef.current = null;
        readyRef.current = false;
      }
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !window.L) return;

    const L = window.L;
    const seen = new Set();
    const bounds = [];

    markers.forEach((m) => {
      if (m.latitude == null || m.longitude == null || m.vehicle_id == null) return;
      const id = m.vehicle_id;
      seen.add(id);
      const latlng = [m.latitude, m.longitude];
      bounds.push(latlng);
      const color = m.online ? (m.moving ? "#16a34a" : "#22c55e") : "#94a3b8";
      const icon = L.divIcon({
        className: "",
        html: `<div style="background:${color};width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4);transition:transform .3s"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      let marker = markerLayerRef.current.get(id);
      if (marker) {
        marker.setLatLng(latlng);
        marker.setIcon(icon);
        marker.setPopupContent(popupHtml(m));
      } else {
        marker = L.marker(latlng, { icon }).addTo(map);
        marker.bindPopup(popupHtml(m));
        markerLayerRef.current.set(id, marker);
      }
    });

    markerLayerRef.current.forEach((marker, id) => {
      if (!seen.has(id)) {
        marker.remove();
        markerLayerRef.current.delete(id);
      }
    });

    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }
    if (route.length > 1) {
      const pts = route
        .filter((p) => p.latitude != null && p.longitude != null)
        .map((p) => [p.latitude, p.longitude]);
      if (pts.length > 1) {
        polylineRef.current = L.polyline(pts, { color: "#2563eb", weight: 3 }).addTo(map);
        pts.forEach((p) => bounds.push(p));
      }
    }

    if (bounds.length === 1 && markerLayerRef.current.size <= 1) {
      map.setView(bounds[0], Math.max(map.getZoom(), 12));
    }
  }, [markers, route]);

  return (
    <div
      ref={containerRef}
      className={`overflow-hidden rounded-3xl border ${className}`}
      style={{ height, width: "100%", zIndex: 0 }}
    />
  );
}
