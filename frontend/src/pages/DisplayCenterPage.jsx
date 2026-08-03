import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const TABS = [
  ["Dashboard", "/display-center"],
  ["Displays", "/display-center/displays"],
  ["Playlists", "/display-center/playlists"],
  ["Widgets", "/display-center/widgets"],
  ["Media Library", "/display-center/media"],
  ["Templates", "/display-center/templates"],
  ["Designer", "/display-center/designer"],
  ["Scheduler", "/display-center/scheduler"],
  ["Monitoring", "/display-center/monitoring"],
  ["Settings", "/display-center/settings"],
];

const CARD_LABELS = {
  online_displays: "Online Displays",
  offline_displays: "Offline Displays",
  active_playlists: "Active Playlists",
  images: "Images",
  videos: "Videos",
  widgets: "Widgets",
};

function tabForPath(pathname) {
  return TABS.find(([, path]) => path !== "/display-center" && pathname.startsWith(path))?.[0] || "Dashboard";
}

export default function DisplayCenterPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState({});
  const [error, setError] = useState("");
  const tab = tabForPath(location.pathname);

  const load = async () => {
    try {
      const [dashboard, displays, playlists, widgets, media, schedules, meta, templates] = await Promise.all([
        api.displayDashboard(), api.displays(), api.displayPlaylists(), api.displayWidgets(),
        api.displayMedia(), api.displaySchedules(), api.displayMeta(), api.displayTemplates(),
      ]);
      setData({ dashboard, displays, playlists, widgets, media, schedules, meta, templates });
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { load(); }, []);

  const addDisplay = async () => {
    const code = `TV-${String((data.displays?.length || 0) + 1).padStart(3, "0")}`;
    await api.createDisplay({ name: `New display ${code}`, code });
    load();
  };
  const addPlaylist = async () => { await api.createDisplayPlaylist({ name: `New playlist ${(data.playlists?.length || 0) + 1}` }); load(); };
  const addWidget = async () => {
    const type = data.meta?.widget_types?.[0] || "clock";
    await api.createDisplayWidget({ key: `${type}-${Date.now()}`, name: "Clock widget", widget_type: type, settings_json: {} });
    load();
  };
  const table = (items, columns) => (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-slate-500"><tr>{columns.map((x) => <th className="px-4 py-3 font-semibold" key={x}>{x}</th>)}</tr></thead>
        <tbody>{(items || []).map((item) => <tr className="border-t" key={item.id}>{columns.map((x) => <td className="px-4 py-3" key={x}>{typeof item[x] === "object" ? JSON.stringify(item[x]) : item[x] ?? "—"}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );

  return <div className="space-y-6 p-4 md:p-7">
    <div><p className="text-sm font-semibold text-blue-600">Enterprise Digital Signage</p><h1 className="text-3xl font-black text-slate-900">📺 Display Center</h1><p className="mt-1 text-slate-500">Factory displays, content, schedules and health monitoring.</p></div>
    {error && <p className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
    <div className="flex gap-2 overflow-x-auto pb-1">{TABS.map(([label, path]) => <button key={path} onClick={() => navigate(path)} className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-semibold ${tab === label ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{label}</button>)}</div>
    {tab === "Dashboard" && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Object.entries(CARD_LABELS).map(([key, label]) => <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200" key={key}><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-3xl font-black">{data.dashboard?.[key] ?? 0}</p></div>)}</div><h2 className="text-lg font-bold">Recent Activity</h2>{table(data.dashboard?.recent_activity, ["display_id", "browser", "connection", "created_at"])}</>}
    {tab === "Displays" && <section className="space-y-4"><button onClick={addDisplay} className="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white">Add display</button>{table(data.displays, ["code", "name", "location", "resolution", "orientation", "status", "last_seen"])}</section>}
    {tab === "Playlists" && <section className="space-y-4"><button onClick={addPlaylist} className="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white">Create playlist</button>{table(data.playlists, ["name", "template_key", "is_active", "updated_at"])}</section>}
    {tab === "Widgets" && <section className="space-y-4"><button onClick={addWidget} className="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white">Create widget</button>{table(data.widgets, ["name", "key", "widget_type", "settings_json", "is_active"])}</section>}
    {tab === "Media Library" && <section className="space-y-4"><label className="inline-block cursor-pointer rounded-xl bg-blue-600 px-4 py-2 font-bold text-white">Upload media<input className="hidden" type="file" onChange={async (e) => { if (e.target.files?.[0]) { await api.uploadDisplayMedia(e.target.files[0]); load(); } }} /></label>{table(data.media, ["name", "media_type", "content_type", "size_bytes", "created_at"])}</section>}
    {tab === "Templates" && <div className="grid gap-3 md:grid-cols-3">{(data.templates || []).map((template) => <button onClick={() => navigate(`/display-center/designer/${template.id}`)} className="rounded-2xl bg-white p-5 text-left shadow-sm ring-1 ring-slate-200" key={template.id}>{template.name}</button>)}</div>}
    {tab === "Designer" && <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200"><p className="font-bold">Choose a template to open the Designer.</p><div className="mt-4 flex flex-wrap gap-2">{(data.templates || []).map((template) => <button onClick={() => navigate(`/display-center/designer/${template.id}`)} className="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white" key={template.id}>{template.name}</button>)}</div></div>}
    {tab === "Scheduler" && table(data.schedules, ["playlist_id", "display_id", "weekdays_json", "start_time", "end_time", "priority", "is_active"])}
    {tab === "Monitoring" && table(data.displays, ["code", "status", "last_seen", "resolution", "ip_address"])}
    {tab === "Settings" && <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200"><p className="font-bold">Global settings API is reserved for plugin-backed configuration.</p><p className="mt-2 text-sm text-slate-500">Refresh interval, default transition, timezone, weather provider and theme are stored as extensible JSON settings.</p></div>}
  </div>;
}
