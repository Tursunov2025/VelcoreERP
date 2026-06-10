import { useEffect, useState } from "react";
import { api } from "../../api/client";
import {
  EXPORT_PERMISSIONS,
  LLP_PERMISSIONS,
  MATERIALS_PERMISSIONS,
  MES_PERMISSIONS,
  PERMISSION_MODULES,
} from "../../constants/permissions";
import Toast from "../ui/Toast";

function isAdminUser(user) {
  return user.role === "admin" || user.department === "Admin";
}

function PermissionMatrix({ users, modules, savingId, onToggle }) {
  return (
    <div className="overflow-x-auto rounded-2xl border bg-white">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50 text-left">
            <th className="px-4 py-3 font-bold">Foydalanuvchi</th>
            {modules.map((m) => (
              <th key={m.id} className="px-3 py-3 text-center font-bold">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.user_id} className="border-b last:border-0">
              <td className="px-4 py-3">
                <p className="font-semibold">{user.username}</p>
                <p className="text-xs text-gray-500">{user.department || user.role}</p>
              </td>
              {modules.map((m) => {
                const enabled = user.permissions?.[m.id];
                const locked = isAdminUser(user);
                return (
                  <td key={m.id} className="px-3 py-3 text-center">
                    <button
                      type="button"
                      disabled={locked || savingId === user.user_id}
                      onClick={() => onToggle(user, m.id)}
                      className={`h-8 w-14 rounded-full transition ${
                        enabled ? "bg-green-500" : "bg-gray-300"
                      } ${locked ? "cursor-not-allowed opacity-60" : "hover:opacity-90"}`}
                    >
                      <span
                        className={`block h-6 w-6 rounded-full bg-white shadow transition ${
                          enabled ? "translate-x-7" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PermissionsTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.adminGetPermissions();
      setUsers(data.users || []);
    } catch (e) {
      setToast(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const togglePermission = async (user, moduleId) => {
    if (isAdminUser(user)) return;
    const next = {
      ...user.permissions,
      [moduleId]: !user.permissions[moduleId],
    };
    setSavingId(user.user_id);
    try {
      await api.adminUpdateUserPermissions(user.user_id, { permissions: next });
      setUsers((prev) =>
        prev.map((u) =>
          u.user_id === user.user_id ? { ...u, permissions: next } : u
        )
      );
      setToast(`${user.username} — ruxsat yangilandi`);
    } catch (e) {
      setToast(e.message);
    } finally {
      setSavingId(null);
    }
  };

  if (loading) return <p>Yuklanmoqda...</p>;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="mb-2 text-xl font-black">Modul ruxsatlari</h2>
        <PermissionMatrix
          users={users}
          modules={PERMISSION_MODULES}
          savingId={savingId}
          onToggle={togglePermission}
        />
      </div>

      <div>
        <h2 className="mb-2 text-xl font-black">LLP (Ichki hujjatlar)</h2>
        <p className="mb-4 text-sm text-gray-500">
          Hujjatlar kutubxonasi uchun alohida ruxsatlar
        </p>
        <PermissionMatrix
          users={users}
          modules={LLP_PERMISSIONS}
          savingId={savingId}
          onToggle={togglePermission}
        />
      </div>

      <div>
        <h2 className="mb-2 text-xl font-black">MES (Production Pro)</h2>
        <p className="mb-4 text-sm text-gray-500">
          Mahsulot shablonlari, detallar va marshrutlar uchun ruxsatlar
        </p>
        <PermissionMatrix
          users={users}
          modules={MES_PERMISSIONS}
          savingId={savingId}
          onToggle={togglePermission}
        />
      </div>

      <div>
        <h2 className="mb-2 text-xl font-black">Xom ashyo ombori</h2>
        <p className="mb-4 text-sm text-gray-500">
          Xom ashyo, qabul/chiqim va inventarizatsiya uchun ruxsatlar
        </p>
        <PermissionMatrix
          users={users}
          modules={MATERIALS_PERMISSIONS}
          savingId={savingId}
          onToggle={togglePermission}
        />
      </div>

      <div>
        <h2 className="mb-2 text-xl font-black">Export hujjatlari</h2>
        <p className="mb-4 text-sm text-gray-500">
          Kazakhstan eksport jo'natmalari va hujjatlarini boshqarish.
        </p>
        <PermissionMatrix
          users={users}
          modules={EXPORT_PERMISSIONS}
          savingId={savingId}
          onToggle={togglePermission}
        />
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
