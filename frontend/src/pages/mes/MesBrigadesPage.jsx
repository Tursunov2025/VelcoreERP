import { useEffect, useMemo, useState } from "react";
import PageHeader from "../../components/ui/PageHeader";
import { api } from "../../api/client";

const EMPTY_FORM = {
  name: "",
  brigadier_user_id: "",
  member_user_ids: [],
  stage_ids: [],
};

function userLabel(user) {
  return [user.full_name || user.username, user.employee_id ? `(${user.employee_id})` : ""]
    .filter(Boolean)
    .join(" ");
}

export default function MesBrigadesPage() {
  const [stages, setStages] = useState([]);
  const [brigades, setBrigades] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadAll = async () => {
    setLoading(true);
    setError("");

    try {
      const [stageData, brigadeData, userData] = await Promise.all([
        api.mesGetStages(false),
        api.mesGetBrigades({ include_inactive: true }),
        api.mesGetBrigadeUsers(),
      ]);

      setStages(
        Array.isArray(stageData)
          ? stageData
          : stageData?.stages || stageData?.items || [],
      );
      setBrigades(brigadeData?.items || []);
      setUsers(userData?.items || []);
    } catch (err) {
      setError(err?.message || "Ma'lumotlarni yuklashda xatolik");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const activeUsers = useMemo(
    () => users.filter((item) => item.is_active),
    [users],
  );

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(false);
  };

  const openCreate = () => {
    setError("");
    setForm({ ...EMPTY_FORM });
    setEditingId(null);
    setShowForm(true);
  };

  const openEdit = (brigade) => {
    setError("");
    setForm({
      name: brigade.name || "",
      brigadier_user_id: String(brigade.brigadier?.id || ""),
      member_user_ids: (brigade.members || []).map((item) => item.id),
      stage_ids: (brigade.terminals || []).map((item) => item.id),
    });
    setEditingId(brigade.id);
    setShowForm(true);
  };

  const toggleTerminal = (stageId) => {
    setForm((current) => {
      const exists = current.stage_ids.includes(stageId);
      return {
        ...current,
        stage_ids: exists
          ? current.stage_ids.filter((id) => id !== stageId)
          : [...current.stage_ids, stageId],
      };
    });
  };

  const toggleMember = (userId) => {
    setForm((current) => {
      const exists = current.member_user_ids.includes(userId);
      return {
        ...current,
        member_user_ids: exists
          ? current.member_user_ids.filter((id) => id !== userId)
          : [...current.member_user_ids, userId],
      };
    });
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");

    try {
      const body = {
        name: form.name.trim(),
        brigadier_user_id: Number(form.brigadier_user_id),
        member_user_ids: form.member_user_ids.map(Number),
        stage_ids: form.stage_ids.map(Number),
      };

      if (!body.name || !body.brigadier_user_id) {
        throw new Error("Brigada nomi va brigadirni tanlang");
      }

      if (editingId) {
        await api.mesUpdateBrigade(editingId, body);
      } else {
        await api.mesCreateBrigade(body);
      }

      resetForm();
      await loadAll();
    } catch (err) {
      setError(err?.message || "Saqlashda xatolik");
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = async (brigade) => {
    setError("");

    try {
      await api.mesSetBrigadeStatus(brigade.id, !brigade.is_active);
      await loadAll();
    } catch (err) {
      setError(err?.message || "Holatni o'zgartirishda xatolik");
    }
  };

  return (
    <div>
      <PageHeader
        title="MES Brigadalar"
        subtitle="Brigadani alohida yarating, keyin istalgan terminal(lar)ga biriktiring."
        actions={
          <button
            type="button"
            onClick={openCreate}
            className="rounded-xl bg-[var(--brand-primary)] px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90"
          >
            + Yangi brigada
          </button>
        }
      />

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={save}
          className="mb-6 rounded-2xl border bg-[var(--brand-card)] p-5 shadow-sm"
        >
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-black">
                {editingId ? "Brigadani tahrirlash" : "Yangi brigada"}
              </h2>
              <p className="mt-1 text-sm text-[var(--brand-muted)]">
                Terminalga bog‘lashni shu oynadan mustaqil boshqaring.
              </p>
            </div>

            <button
              type="button"
              onClick={resetForm}
              className="rounded-lg border px-3 py-2 text-sm font-semibold"
            >
              Bekor qilish
            </button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold">
                Brigada nomi
              </span>
              <input
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                placeholder="Masalan: Alfa"
                className="w-full rounded-xl border bg-white px-3 py-2.5"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold">
                Brigadir
              </span>
              <select
                value={form.brigadier_user_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    brigadier_user_id: event.target.value,
                  }))
                }
                className="w-full rounded-xl border bg-white px-3 py-2.5"
              >
                <option value="">Brigadirni tanlang</option>
                {activeUsers.map((user) => (
                  <option key={user.id} value={user.id}>
                    {userLabel(user)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold">Terminallar</div>
              <div className="text-xs text-gray-500">
                {form.stage_ids.length} ta tanlangan
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {stages.map((stage) => {
                const selected = form.stage_ids.includes(stage.id);

                return (
                  <label
                    key={stage.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 transition ${
                      selected
                        ? "border-[var(--brand-primary)] bg-[var(--brand-secondary)]"
                        : "bg-white hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleTerminal(stage.id)}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold">
                        {stage.name}
                      </div>
                      {stage.department && (
                        <div className="truncate text-xs text-gray-500">
                          {stage.department}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>

            <p className="mt-2 text-xs text-gray-500">
              Brigada bir vaqtning o‘zida bir nechta terminalga biriktirilishi mumkin.
            </p>
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold">Brigada ishchilari</span>
              <span className="text-xs text-gray-500">
                {form.member_user_ids.length} ta tanlangan
              </span>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {activeUsers.map((user) => {
                const selected = form.member_user_ids.includes(user.id);

                return (
                  <label
                    key={user.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 transition ${
                      selected
                        ? "border-[var(--brand-primary)] bg-[var(--brand-secondary)]"
                        : "bg-white hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleMember(user.id)}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold">
                        {user.full_name || user.username}
                      </div>
                      <div className="truncate text-xs text-gray-500">
                        {user.employee_id || user.position || user.username}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-[var(--brand-primary)] px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50"
            >
              {saving ? "Saqlanmoqda..." : "Saqlash"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="rounded-2xl border bg-[var(--brand-card)] p-8 text-center text-sm text-gray-500">
          Yuklanmoqda...
        </div>
      ) : brigades.length === 0 ? (
        <div className="rounded-2xl border bg-[var(--brand-card)] p-10 text-center">
          <div className="text-4xl">👥</div>
          <h2 className="mt-3 text-lg font-black">
            Hali brigadalar yaratilmagan
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Birinchi brigadani yaratish uchun yuqoridagi tugmadan foydalaning.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {brigades.map((brigade) => (
            <div
              key={brigade.id}
              className="rounded-2xl border bg-[var(--brand-card)] p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {brigade.terminals?.length
                      ? `${brigade.terminals.length} ta terminal`
                      : "Terminal biriktirilmagan"}
                  </div>
                  <h3 className="mt-1 text-lg font-black">{brigade.name}</h3>
                </div>

                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                    brigade.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {brigade.is_active ? "Aktiv" : "Inaktiv"}
                </span>
              </div>

              <div className="mt-4">
                <div className="mb-2 text-xs font-semibold text-gray-500">
                  TERMINALLAR
                </div>

                <div className="flex flex-wrap gap-2">
                  {(brigade.terminals || []).map((terminal) => (
                    <span
                      key={terminal.id}
                      className="rounded-lg border bg-white px-2.5 py-1.5 text-xs font-bold"
                    >
                      {terminal.name}
                    </span>
                  ))}
                  {!brigade.terminals?.length && (
                    <span className="text-sm text-gray-500">
                      Hali biriktirilmagan
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-gray-50 p-3">
                <div className="text-xs font-semibold text-gray-500">
                  Brigadir
                </div>
                <div className="mt-1 text-sm font-bold">
                  {brigade.brigadier
                    ? userLabel(brigade.brigadier)
                    : "Belgilanmagan"}
                </div>
              </div>

              <div className="mt-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500">
                    Ishchilar
                  </span>
                  <span className="text-xs font-bold">
                    {brigade.members?.length || 0} ta
                  </span>
                </div>

                <div className="space-y-1.5">
                  {(brigade.members || []).map((member) => (
                    <div
                      key={member.id}
                      className="rounded-lg border bg-white px-3 py-2 text-sm"
                    >
                      <div className="font-semibold">
                        {member.full_name || member.username}
                      </div>
                      {(member.employee_id || member.position) && (
                        <div className="text-xs text-gray-500">
                          {member.employee_id || member.position}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  onClick={() => openEdit(brigade)}
                  className="flex-1 rounded-xl border px-3 py-2 text-sm font-bold"
                >
                  Tahrirlash
                </button>
                <button
                  type="button"
                  onClick={() => toggleStatus(brigade)}
                  className="rounded-xl border px-3 py-2 text-sm font-bold"
                >
                  {brigade.is_active ? "O‘chirish" : "Aktivlashtirish"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
