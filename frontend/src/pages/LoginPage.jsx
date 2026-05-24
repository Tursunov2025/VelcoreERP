import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useUsers } from "../hooks/useUsers";

const ROLE_LABELS = { admin: "Admin", operator: "Operator" };

export default function LoginPage() {
  const { login, loginError, isSubmitting } = useAuth();
  const { users, loading, error, fetchUsers } = useUsers({ enabled: true });
  const [loginUser, setLoginUser] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    await login(loginUser, loginPassword);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f6fa] p-4">
      <div className="w-full max-w-md rounded-[40px] bg-white p-8 shadow-2xl md:p-10">
        <h1 className="mb-2 text-center text-3xl font-black md:text-4xl">Azmus ERP</h1>
        <p className="mb-8 text-center text-sm text-gray-500">
          Professional CRM / ERP tizimi
        </p>
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-600">
              Foydalanuvchi
            </label>
            <select
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              disabled={loading}
              className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
            >
              <option value="">{loading ? "Yuklanmoqda..." : "User tanlang"}</option>
              {users.map((user) => (
                <option key={user.username} value={user.username}>
                  {user.username} — {ROLE_LABELS[user.role] || user.role}
                </option>
              ))}
            </select>
            {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-600">Parol</label>
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              placeholder="Parol"
              className="w-full rounded-2xl border px-5 py-4 outline-none focus:ring-2 focus:ring-black"
            />
          </div>
          {loginError && <p className="text-sm text-red-500">{loginError}</p>}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-2xl bg-black py-4 font-bold text-white disabled:opacity-60"
          >
            {isSubmitting ? "Kirish..." : "Kirish"}
          </button>
          <button
            type="button"
            onClick={fetchUsers}
            className="w-full text-sm text-gray-500 hover:text-black"
          >
            Foydalanuvchilarni yangilash
          </button>
        </form>
      </div>
    </div>
  );
}
