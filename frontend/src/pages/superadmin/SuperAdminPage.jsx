import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import AdminRoute from "../../components/layout/AdminRoute";
import { invalidateUiConfigCache } from "../../hooks/useUiConfig";

const SECTIONS = [
  { id: "navigation", label: "Menyu", icon: "📋" },
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "modules", label: "Modullar", icon: "🧩" },
  { id: "theme", label: "Theme", icon: "🎨" },
  { id: "forms", label: "Form Builder", icon: "📝" },
  { id: "tables", label: "Table Builder", icon: "📑" },
  { id: "roles", label: "Rollar", icon: "🔐" },
  { id: "audit", label: "Audit Log", icon: "📜" },
  { id: "versions", label: "Versiyalar", icon: "⏪" },
];

const FIELD_TYPES = ["text", "number", "select", "checkbox", "barcode", "qr"];

function toast(msg) {
  window.dispatchEvent(new CustomEvent("velcore-toast", { detail: msg }));
}

export default function SuperAdminPage() {
  const [section, setSection] = useState("navigation");
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.superAdminConfig();
      setConfig(data);
    } catch (e) {
      toast(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const applyLive = useCallback(async () => {
    invalidateUiConfigCache();
    await reload();
  }, [reload]);

  const flatNav = useMemo(() => {
    const out = [];
    const walk = (nodes) => {
      (nodes || []).forEach((n) => {
        out.push(n);
        walk(n.children);
      });
    };
    walk(config?.navigation_all || []);
    return out;
  }, [config]);

  if (loading && !config) {
    return (
      <AdminRoute>
        <div className="flex min-h-[60vh] items-center justify-center">
          <p className="text-[var(--brand-muted)]">Super Admin yuklanmoqda…</p>
        </div>
      </AdminRoute>
    );
  }

  return (
    <AdminRoute>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-[var(--brand-text)]">Super Admin CMS</h1>
          <p className="text-sm text-[var(--brand-muted)]">
            Odoo / Bitrix24 darajasidagi tizim boshqaruvi — kod yozmasdan
          </p>
        </div>
        <button
          type="button"
          onClick={async () => {
            setSaving(true);
            try {
              await api.superAdminSnapshot("Manual snapshot");
              toast("Snapshot saqlandi");
              await applyLive();
            } catch (e) {
              toast(e.message);
            } finally {
              setSaving(false);
            }
          }}
          disabled={saving}
          className="rounded-xl px-4 py-2 text-sm font-bold text-white"
          style={{ backgroundColor: "var(--brand-button)" }}
        >
          💾 Snapshot
        </button>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="shrink-0 lg:w-56">
          <nav className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSection(s.id)}
                className={`flex shrink-0 items-center gap-2 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition ${
                  section === s.id ? "bg-black text-white" : "bg-white text-gray-700 hover:bg-gray-100"
                }`}
              >
                <span>{s.icon}</span>
                {s.label}
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 flex-1 rounded-3xl border bg-[var(--brand-card)] p-5 shadow-sm">
          {section === "navigation" && (
            <NavigationPanel flatNav={flatNav} onSaved={applyLive} />
          )}
          {section === "dashboard" && (
            <DashboardPanel widgets={config?.widgets_all || []} onSaved={applyLive} />
          )}
          {section === "modules" && (
            <ModulesPanel modules={config?.modules_all || []} onSaved={applyLive} />
          )}
          {section === "theme" && (
            <ThemePanel themes={config?.themes || []} onSaved={applyLive} />
          )}
          {section === "forms" && <FormsPanel onSaved={applyLive} />}
          {section === "tables" && <TablesPanel onSaved={applyLive} />}
          {section === "roles" && (
            <RolesPanel roles={config?.roles || []} permissions={config?.permissions || []} onSaved={applyLive} />
          )}
          {section === "audit" && <AuditPanel />}
          {section === "versions" && (
            <VersionsPanel versions={config?.versions || []} onRollback={applyLive} />
          )}
        </div>
      </div>
    </AdminRoute>
  );
}

function NavigationPanel({ flatNav, onSaved }) {
  const [newItem, setNewItem] = useState({
    nav_key: "",
    label: "",
    emoji: "📌",
    path: "/",
    sort_order: 50,
  });

  const update = async (id, patch) => {
    try {
      await api.superAdminUpdateNav(id, patch);
      toast("Menyu yangilandi");
      await onSaved();
    } catch (e) {
      toast(e.message);
    }
  };

  const add = async () => {
    if (!newItem.nav_key.trim() || !newItem.label.trim()) return;
    try {
      await api.superAdminCreateNav(newItem);
      setNewItem({ nav_key: "", label: "", emoji: "📌", path: "/", sort_order: 50 });
      toast("Menyu qo'shildi");
      await onSaved();
    } catch (e) {
      toast(e.message);
    }
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Menyu boshqaruvi</h2>
      <div className="mb-6 grid gap-2 rounded-2xl border bg-gray-50 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <input
          placeholder="nav_key"
          value={newItem.nav_key}
          onChange={(e) => setNewItem({ ...newItem, nav_key: e.target.value })}
          className="rounded-xl border px-3 py-2 text-sm"
        />
        <input
          placeholder="Nomi"
          value={newItem.label}
          onChange={(e) => setNewItem({ ...newItem, label: e.target.value })}
          className="rounded-xl border px-3 py-2 text-sm"
        />
        <input
          placeholder="Emoji"
          value={newItem.emoji}
          onChange={(e) => setNewItem({ ...newItem, emoji: e.target.value })}
          className="rounded-xl border px-3 py-2 text-sm"
        />
        <input
          placeholder="URL"
          value={newItem.path}
          onChange={(e) => setNewItem({ ...newItem, path: e.target.value })}
          className="rounded-xl border px-3 py-2 text-sm"
        />
        <button type="button" onClick={add} className="rounded-xl bg-black px-3 py-2 text-sm font-bold text-white">
          + Qo'shish
        </button>
      </div>
      <div className="space-y-3">
        {flatNav.map((item) => (
          <div key={item.id} className="rounded-2xl border p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="text-sm">
                <span className="text-xs text-gray-500">Nomi</span>
                <input
                  defaultValue={item.label}
                  onBlur={(e) => update(item.id, { label: e.target.value })}
                  className="mt-1 w-full rounded-xl border px-3 py-2"
                />
              </label>
              <label className="text-sm">
                <span className="text-xs text-gray-500">Emoji / Icon</span>
                <input
                  defaultValue={item.emoji}
                  onBlur={(e) => update(item.id, { emoji: e.target.value })}
                  className="mt-1 w-full rounded-xl border px-3 py-2"
                />
              </label>
              <label className="text-sm">
                <span className="text-xs text-gray-500">URL</span>
                <input
                  defaultValue={item.path}
                  onBlur={(e) => update(item.id, { path: e.target.value })}
                  className="mt-1 w-full rounded-xl border px-3 py-2"
                />
              </label>
              <label className="text-sm">
                <span className="text-xs text-gray-500">Rang</span>
                <input
                  type="color"
                  defaultValue={item.color || "#6366f1"}
                  onBlur={(e) => update(item.id, { color: e.target.value })}
                  className="mt-1 h-10 w-full rounded-xl border"
                />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={item.visible}
                  onChange={(e) => update(item.id, { visible: e.target.checked })}
                />
                Ko'rinadi
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={item.hidden}
                  onChange={(e) => update(item.id, { hidden: e.target.checked })}
                />
                Yashirin
              </label>
              <span className="text-gray-400">{item.nav_key}</span>
              <button
                type="button"
                className="text-red-600"
                onClick={async () => {
                  if (!window.confirm(`"${item.label}" o'chirilsinmi?`)) return;
                  await api.superAdminDeleteNav(item.id);
                  await onSaved();
                }}
              >
                O'chirish
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardPanel({ widgets, onSaved }) {
  const toggle = async (w) => {
    await api.superAdminUpsertWidget({
      widget_key: w.widget_key,
      title: w.title,
      widget_type: w.widget_type,
      enabled: !w.enabled,
      sort_order: w.sort_order,
      color: w.color,
      layout: w.layout || {},
      config: w.config || {},
    });
    await onSaved();
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Dashboard widgetlari</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {widgets.map((w) => (
          <div key={w.widget_key} className="rounded-2xl border p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold">{w.title}</p>
                <p className="text-xs text-gray-500">{w.widget_type} · {w.widget_key}</p>
              </div>
              <button
                type="button"
                onClick={() => toggle(w)}
                className={`rounded-full px-3 py-1 text-xs font-bold ${w.enabled ? "bg-green-100 text-green-700" : "bg-gray-100"}`}
              >
                {w.enabled ? "Yoniq" : "O'chiq"}
              </button>
            </div>
            <input
              type="color"
              defaultValue={w.color || "#6366f1"}
              className="mt-2 h-8 w-full"
              onBlur={async (e) => {
                await api.superAdminUpsertWidget({ ...w, color: e.target.value, layout: w.layout || {}, config: w.config || {} });
                await onSaved();
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function ModulesPanel({ modules, onSaved }) {
  const save = async (m) => {
    await api.superAdminUpdateModule(m.id, {
      module_key: m.module_key,
      label: m.label,
      icon: m.icon,
      color: m.color,
      url: m.url,
      enabled: m.enabled,
      permissions: m.permissions || [],
      sort_order: m.sort_order,
    });
    toast("Modul yangilandi");
    await onSaved();
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Modul boshqaruvi</h2>
      <div className="space-y-3">
        {modules.map((m) => (
          <ModuleRow key={m.module_key} module={m} onSave={save} />
        ))}
      </div>
    </div>
  );
}

function ModuleRow({ module: m, onSave }) {
  const [draft, setDraft] = useState(m);
  useEffect(() => setDraft(m), [m]);
  return (
    <div className="rounded-2xl border p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input value={draft.icon} onChange={(e) => setDraft({ ...draft, icon: e.target.value })} className="rounded-xl border px-3 py-2" />
        <input value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} className="rounded-xl border px-3 py-2" />
        <input value={draft.url} onChange={(e) => setDraft({ ...draft, url: e.target.value })} className="rounded-xl border px-3 py-2" />
        <input type="color" value={draft.color || "#6366f1"} onChange={(e) => setDraft({ ...draft, color: e.target.value })} className="h-10 rounded-xl border" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={draft.enabled} onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} />
          Yoqilgan
        </label>
      </div>
      <button type="button" onClick={() => onSave(draft)} className="mt-3 rounded-xl bg-black px-4 py-2 text-sm font-bold text-white">
        Saqlash
      </button>
    </div>
  );
}

function ThemePanel({ themes, onSaved }) {
  const active = themes.find((t) => t.is_active) || themes[0];
  const [draft, setDraft] = useState(active?.config || {});

  useEffect(() => {
    if (active?.config) setDraft(active.config);
  }, [active]);

  const save = async () => {
    if (!active) return;
    await api.superAdminUpdateTheme(active.id, {
      name: active.name,
      is_dark: active.is_dark,
      config: draft,
    });
    toast("Theme saqlandi — real vaqtda qo'llaniladi");
    await onSaved();
  };

  const keys = [
    ["primary_color", "Primary"],
    ["secondary_color", "Secondary"],
    ["sidebar_color", "Sidebar"],
    ["card_color", "Card"],
    ["button_color", "Button"],
    ["background_color", "Background"],
    ["text_color", "Text"],
    ["font_size_base", "Font size"],
    ["border_radius", "Border radius"],
  ];

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">UI Theme Manager</h2>
      <div className="mb-4 flex flex-wrap gap-2">
        {themes.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={async () => {
              await api.superAdminActivateTheme(t.id);
              await onSaved();
            }}
            className={`rounded-xl px-4 py-2 text-sm font-bold ${t.is_active ? "bg-black text-white" : "border"}`}
          >
            {t.name} {t.is_dark ? "🌙" : "☀️"}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {keys.map(([key, label]) => (
          <label key={key} className="text-sm">
            <span className="text-xs text-gray-500">{label}</span>
            {key.includes("color") ? (
              <input
                type="color"
                value={draft[key] || "#6366f1"}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                className="mt-1 h-10 w-full rounded-xl border"
              />
            ) : (
              <input
                value={draft[key] || ""}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                className="mt-1 w-full rounded-xl border px-3 py-2"
              />
            )}
          </label>
        ))}
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            checked={Boolean(draft.animations_enabled)}
            onChange={(e) => setDraft({ ...draft, animations_enabled: e.target.checked })}
          />
          Animatsiyalar
        </label>
      </div>
      <button type="button" onClick={save} className="mt-4 rounded-xl bg-black px-4 py-2 text-sm font-bold text-white">
        Theme saqlash
      </button>
    </div>
  );
}

function FormsPanel({ onSaved }) {
  const [forms, setForms] = useState([]);

  useEffect(() => {
    api.superAdminGetForms().then((r) => setForms(r.forms || [])).catch(() => setForms([]));
  }, []);

  const addForm = () => {
    setForms([
      ...forms,
      {
        form_key: `form_${Date.now()}`,
        title: "Yangi forma",
        fields: [{ name: "field1", label: "Maydon", type: "text" }],
      },
    ]);
  };

  const addField = (fi) => {
    const next = [...forms];
    next[fi].fields.push({ name: `f_${Date.now()}`, label: "Yangi maydon", type: "text" });
    setForms(next);
  };

  const save = async () => {
    await api.superAdminSaveForms(forms);
    toast("Formalar saqlandi");
    await onSaved();
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Dynamic Form Builder</h2>
      <div className="mb-4 flex gap-2">
        <button type="button" onClick={addForm} className="rounded-xl border px-4 py-2 text-sm font-bold">
          + Forma
        </button>
        <button type="button" onClick={save} className="rounded-xl bg-black px-4 py-2 text-sm font-bold text-white">
          Saqlash
        </button>
      </div>
      {forms.map((form, fi) => (
        <div key={form.form_key} className="mb-4 rounded-2xl border p-4">
          <input
            value={form.title}
            onChange={(e) => {
              const n = [...forms];
              n[fi].title = e.target.value;
              setForms(n);
            }}
            className="mb-3 w-full rounded-xl border px-3 py-2 font-bold"
          />
          {form.fields.map((field, idx) => (
            <div key={idx} className="mb-2 grid gap-2 sm:grid-cols-3">
              <input
                value={field.label}
                onChange={(e) => {
                  const n = [...forms];
                  n[fi].fields[idx].label = e.target.value;
                  setForms(n);
                }}
                className="rounded-xl border px-3 py-2 text-sm"
                placeholder="Label"
              />
              <select
                value={field.type}
                onChange={(e) => {
                  const n = [...forms];
                  n[fi].fields[idx].type = e.target.value;
                  setForms(n);
                }}
                className="rounded-xl border px-3 py-2 text-sm"
              >
                {FIELD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button type="button" onClick={() => addField(fi)} className="text-sm text-blue-600">
            + Maydon
          </button>
        </div>
      ))}
    </div>
  );
}

function TablesPanel({ onSaved }) {
  const [tables, setTables] = useState([]);

  useEffect(() => {
    api.superAdminGetTables().then((r) => setTables(r.tables || [])).catch(() => setTables([]));
  }, []);

  const addTable = () => {
    setTables([
      ...tables,
      {
        table_key: `table_${Date.now()}`,
        title: "Yangi jadval",
        columns: [{ key: "col1", label: "Ustun" }],
        filters: [],
        export: ["excel", "pdf"],
      },
    ]);
  };

  const save = async () => {
    await api.superAdminSaveTables(tables);
    toast("Jadvallar saqlandi");
    await onSaved();
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Dynamic Table Builder</h2>
      <div className="mb-4 flex gap-2">
        <button type="button" onClick={addTable} className="rounded-xl border px-4 py-2 text-sm font-bold">
          + Jadval
        </button>
        <button type="button" onClick={save} className="rounded-xl bg-black px-4 py-2 text-sm font-bold text-white">
          Saqlash
        </button>
      </div>
      {tables.map((tbl, ti) => (
        <div key={tbl.table_key} className="mb-4 rounded-2xl border p-4">
          <input
            value={tbl.title}
            onChange={(e) => {
              const n = [...tables];
              n[ti].title = e.target.value;
              setTables(n);
            }}
            className="mb-3 w-full rounded-xl border px-3 py-2 font-bold"
          />
          {tbl.columns.map((col, ci) => (
            <input
              key={ci}
              value={col.label}
              onChange={(e) => {
                const n = [...tables];
                n[ti].columns[ci].label = e.target.value;
                setTables(n);
              }}
              className="mb-2 w-full rounded-xl border px-3 py-2 text-sm"
            />
          ))}
          <button
            type="button"
            onClick={() => {
              const n = [...tables];
              n[ti].columns.push({ key: `c_${Date.now()}`, label: "Ustun" });
              setTables(n);
            }}
            className="text-sm text-blue-600"
          >
            + Ustun
          </button>
        </div>
      ))}
    </div>
  );
}

function RolesPanel({ roles, permissions, onSaved }) {
  const [activeRole, setActiveRole] = useState(roles[0]?.id);
  const role = roles.find((r) => r.id === activeRole);

  const toggle = async (key, enabled) => {
    if (!role) return;
    const next = { ...role.permissions, [key]: enabled };
    await api.superAdminUpdateRolePermissions(role.id, { permissions: next });
    toast("Ruxsat yangilandi");
    await onSaved();
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Rollar va ruxsatlar</h2>
      <div className="mb-4 flex flex-wrap gap-2">
        {roles.map((r) => (
          <button
            key={r.id}
            type="button"
            onClick={() => setActiveRole(r.id)}
            className={`rounded-xl px-4 py-2 text-sm font-bold ${activeRole === r.id ? "bg-black text-white" : "border"}`}
          >
            {r.label}
          </button>
        ))}
      </div>
      <div className="max-h-[420px] overflow-y-auto rounded-2xl border p-3">
        {permissions.map((p) => (
          <label key={p.perm_key} className="flex items-center justify-between border-b py-2 text-sm">
            <span>{p.label || p.perm_key}</span>
            <input
              type="checkbox"
              checked={Boolean(role?.permissions?.[p.perm_key])}
              onChange={(e) => toggle(p.perm_key, e.target.checked)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function AuditPanel() {
  const [logs, setLogs] = useState([]);
  useEffect(() => {
    api.superAdminAuditLogs({ limit: 100 }).then((r) => setLogs(r.logs || []));
  }, []);

  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Audit Log</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase text-gray-500">
              <th className="p-2">Vaqt</th>
              <th className="p-2">Kim</th>
              <th className="p-2">Amal</th>
              <th className="p-2">Eski</th>
              <th className="p-2">Yangi</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-b">
                <td className="p-2 whitespace-nowrap">{l.created_at?.slice(0, 19)}</td>
                <td className="p-2">{l.username}</td>
                <td className="p-2">{l.action} · {l.entity_type}</td>
                <td className="max-w-[120px] truncate p-2 text-xs">{l.old_value}</td>
                <td className="max-w-[120px] truncate p-2 text-xs">{l.new_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VersionsPanel({ versions, onRollback }) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-bold">Versiyalar — rollback</h2>
      <div className="space-y-2">
        {versions.map((v) => (
          <div key={v.id} className="flex items-center justify-between rounded-2xl border p-4">
            <div>
              <p className="font-bold">{v.label || `Version #${v.id}`}</p>
              <p className="text-xs text-gray-500">{v.created_by} · {v.created_at?.slice(0, 19)}</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                if (!window.confirm("Ushbu versiyaga qaytarilsinmi?")) return;
                await api.superAdminRollback(v.id);
                toast("Rollback bajarildi");
                await onRollback();
              }}
              className="rounded-xl border px-4 py-2 text-sm font-bold"
            >
              ⏪ Qaytarish
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
