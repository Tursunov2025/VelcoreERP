import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { DEPARTMENTS } from "../../constants/workflow";
import ConfirmDialog from "../ui/ConfirmDialog";
import Toast from "../ui/Toast";
import { useLocale } from "../../context/LocaleContext";

export default function UsersTab() {
  const { t } = useLocale();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [form, setForm] = useState({
    username: "",
    password: "",
    role: "operator",
    department: "Kesish",
    is_active: true,
  });

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await api.adminGetUsers());
    } catch (e) {
      setToast(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openCreate = () => {
    setForm({
      username: "",
      password: "",
      role: "operator",
      department: "Kesish",
      is_active: true,
    });
    setModal("create");
  };

  const openEdit = (user) => {
    setForm({
      id: user.id,
      username: user.username,
      password: "",
      role: user.role,
      department: user.department,
      is_active: user.is_active !== false,
    });
    setModal("edit");
  };

  const save = async () => {
    try {
      if (modal === "create") {
        await api.adminCreateUser(form);
        setToast(t("legacySettings.users.created"));
      } else {
        await api.adminUpdateUser(form.id, {
          username: form.username,
          role: form.role,
          department: form.department,
          is_active: form.is_active,
        });
        if (form.password) {
          await api.adminResetPassword(form.id, { password: form.password });
        }
        setToast(t("legacySettings.saved"));
      }
      setModal(null);
      load();
    } catch (e) {
      setToast(e.message);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-black">{t("settingsNav.users")}</h2>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-2xl bg-black px-5 py-2 text-sm text-white"
        >
          {t("legacySettings.users.addOperator")}
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">{t("common.loading")}</p>
      ) : (
        <div className="space-y-3">
          {users.map((user) => (
            <div
              key={user.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-white p-4"
            >
              <div>
                <p className="font-bold">{user.username}</p>
                <p className="text-sm text-gray-500">
                  {user.role} · {user.department}
                </p>
                <span
                  className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${
                    user.is_active !== false
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {user.is_active !== false ? t("common.active") : t("common.inactive")}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => openEdit(user)}
                  className="rounded-xl border px-4 py-2 text-sm"
                >
                  {t("common.edit")}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setConfirm({
                      title: t("common.delete"),
                      message: t("legacySettings.users.deleteConfirm", { username: user.username }),
                      onConfirm: async () => {
                        await api.adminDeleteUser(user.id);
                        setToast(t("legacySettings.users.deleted"));
                        setConfirm(null);
                        load();
                      },
                    })
                  }
                  className="rounded-xl bg-red-500 px-4 py-2 text-sm text-white"
                >
                  {t("common.delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-[28px] bg-white p-6">
            <h3 className="mb-4 text-lg font-black">
              {modal === "create" ? t("users.createUser") : t("users.editUser")}
            </h3>
            <div className="space-y-3">
              <input
                placeholder={t("users.username")}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
              />
              <input
                type="password"
                placeholder={modal === "edit" ? t("users.newPassword") : t("users.password")}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
              />
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
              >
                <option value="operator">{t("roleNames.operator")}</option>
                <option value="admin">{t("roleNames.admin")}</option>
              </select>
              <select
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
                className="w-full rounded-xl border px-4 py-3"
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                {t("common.active")}
              </label>
            </div>
            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => setModal(null)}
                className="flex-1 rounded-xl border py-3"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={save}
                className="flex-1 rounded-xl bg-black py-3 text-white"
              >
                {t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.title}
        message={confirm?.message}
        danger
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
      />
      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
