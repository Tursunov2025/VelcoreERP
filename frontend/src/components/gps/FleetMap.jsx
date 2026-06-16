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

function formatAge(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

/**
 * OpenStreetMap fleet map with vehicle markers and optional route polyline.
 * markers: [{ latitude, longitude, plate_number, driver_name, online, seconds_since_update, speed }]
 * route: [{ latitude, longitude }]
 */
export default function FleetMap({ markers = [], route = [], height = "420px", className = "" }) {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const layerRef = useRef({ markers: [], polyline: null });

  useEffect(() => {
    let map;
    let cancelled = false;

    loadLeaflet()
      .then((L) => {
        if (cancelled || !containerRef.current) return;
        if (mapRef.current) {
          mapRef.current.remove();
          mapRef.current = null;
        }

        const defaultCenter = [41.2995, 69.2401];
        map = L.map(containerRef.current).setView(defaultCenter, 6);
        mapRef.current = map;

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap",
          maxZoom: 19,
        }).addTo(map);

        layerRef.current.markers.forEach((m) => m.remove());
        layerRef.current.markers = [];
        if (layerRef.current.polyline) {
          layerRef.current.polyline.remove();
          layerRef.current.polyline = null;
        }

        const bounds = [];

        markers.forEach((m) => {
          if (m.latitude == null || m.longitude == null) return;
          const latlng = [m.latitude, m.longitude];
          bounds.push(latlng);
          const color = m.online ? "#16a34a" : "#94a3b8";
          const icon = L.divIcon({
            className: "",
            html: `<div style="background:${color};width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          });
          const marker = L.marker(latlng, { icon }).addTo(map);
          marker.bindPopup(
            `<strong>${m.plate_number || "Vehicle"}</strong><br/>` +
              `${m.driver_name || "—"}<br/>` +
              `Speed: ${m.speed ?? 0} km/h<br/>` +
              `Updated: ${formatAge(m.seconds_since_update)}`
          );
          layerRef.current.markers.push(marker);
        });

        if (route.length > 1) {
          const pts = route
            .filter((p) => p.latitude != null && p.longitude != null)
            .map((p) => [p.latitude, p.longitude]);
          if (pts.length > 1) {
            layerRef.current.polyline = L.polyline(pts, { color: "#2563eb", weight: 3 }).addTo(map);
            pts.forEach((p) => bounds.push(p));
          }
        }

        if (bounds.length === 1) map.setView(bounds[0], 12);
        else if (bounds.length > 1) map.fitBounds(bounds, { padding: [40, 40] });
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [markers, route]);

  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`overflow-hidden rounded-3xl border ${className}`}
      style={{ height, width: "100%", zIndex: 0 }}
    />
  );
}
