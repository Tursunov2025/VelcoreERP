import { useMemo, useRef, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { api } from "../../api/client";
import { buildUserIdentityPayload, normalizeUserIdentityDefaults } from "../../utils/userIdentityPayload";
import { useLocale } from "../../context/LocaleContext";
import { localizedCanonical } from "../../i18n/displayLabels";
import RolesTab from "./RolesTab";
import SecurityTab from "./SecurityTab";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, retry: 1 } },
});
const sections = ["users", "roles", "departments", "activity", "sessions", "passwordPolicy"];
const input =
  "rounded-xl border border-[var(--brand-muted)]/30 bg-transparent px-3 py-2 text-sm text-[var(--brand-text)] outline-none focus:border-[var(--brand-primary)]";

function Skeleton() {
  return (
    <div className="space-y-3 p-5">
      {Array.from({ length: 6 }, (_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-2xl bg-black/5 dark:bg-white/10"
        />
      ))}
    </div>
  );
}
function UserDialog({ user, onClose, roleOptions = [], departments = [] }) {
  const { t } = useLocale();
  const passwordIntent = useRef(false);
  const cache = useQueryClient();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, dirtyFields },
  } = useForm({
    defaultValues: normalizeUserIdentityDefaults(user),
  });
  const mutation = useMutation({
    mutationFn: (data) =>
      user
        ? api.updateIdentityUser(user.id, data)
        : api.createIdentityUser(data),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["identity-users"], refetchType: "active" });
      onClose();
    },
    onError: (error) => {
      Object.keys(error?.fieldErrors || {}).forEach((name) =>
        setError(name, { type: "server", message: name === "password" ? t("userMessages.minimumPassword") : name === "email" ? t("userMessages.invalidEmail") : name === "username" ? t("userMessages.usernameRequired") : t("userMessages.validationSummary") }),
      );
    },
  });
  const submit = (data) => {
    const payload = buildUserIdentityPayload(data, {
      passwordIntent: passwordIntent.current,
      passwordDirty: Boolean(dirtyFields.password),
    });
    mutation.mutate(payload);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/50 p-3 sm:items-center sm:justify-center">
      <form
        onSubmit={handleSubmit(submit)}
        className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-[var(--brand-card)] p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black text-[var(--brand-text)]">
            {t(user ? "users.editUser" : "users.createUser")}
          </h3>
          <button type="button" onClick={onClose} className="text-xl">
            ×
          </button>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {[
            [t("users.fullName"), "full_name"], [t("users.username"), "username"], [t("users.employeeId"), "employee_id"], [t("users.position"), "position"], [t("users.phone"), "phone"], [t("users.email"), "email"], [t("users.telegram"), "telegram"],
          ].map(([label, name]) => (
            <label
              key={name}
              className="text-sm font-medium text-[var(--brand-text)]"
            >
              {label}
              <input
                className={`${input} mt-1 w-full`}
                {...register(
                  name,
                  name === "username"
                    ? { required: t("userMessages.usernameRequired"), minLength: { value: 2, message: t("userMessages.usernameRequired") } }
                    : name === "email"
                      ? {
                          pattern: {
                            value: /^$|^\S+@\S+\.\S+$/,
                            message: t("userMessages.invalidEmail"),
                          },
                        }
                      : {},
                )}
              />
              {errors[name]?.message ? <span className="mt-1 block text-xs text-red-500">{errors[name].message}</span> : null}
            </label>
          ))}
          <label className="text-sm font-medium text-[var(--brand-text)]">
            {t("users.department")}
            <select className={`${input} mt-1 w-full`} {...register("department", { required: true })}>
              <option value="">{t("platformAdministration.selectDepartment")}</option>
              {departments.map((department) => <option key={department} value={department}>{localizedCanonical(t, "departmentNames", department)}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-[var(--brand-text)]">
            {t("platformAdministration.role")}
            <select className={`${input} mt-1 w-full`} {...register("role")}>
              {roleOptions.map((role) => <option key={role.key} value={role.key}>{role.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-[var(--brand-text)]">
            {t(user ? "users.newPassword" : "users.password")}
            <input
              className={`${input} mt-1 w-full`}
              type="password"
              autoComplete="new-password"
              onKeyDown={() => { passwordIntent.current = true; }}
              onPaste={() => { passwordIntent.current = true; }}
              {...register(
                "password",
                user
                  ? { validate: (value) => !value || value.length >= 8 || t("userMessages.minimumPassword") }
                  : {
                      required: t("userMessages.passwordRequired"), minLength: { value: 8, message: t("userMessages.minimumPassword") },
                    },
              )}
            />
            {errors.password?.message ? <span className="mt-1 block text-xs text-red-500">{errors.password.message}</span> : null}
          </label>
          <label className="flex items-center gap-2 text-sm text-[var(--brand-text)]">
            <input type="checkbox" {...register("is_active")} /> {t("platformAdministration.activeAccount")}
          </label>
        </div>
        {mutation.error && Object.keys(mutation.error.fieldErrors || {}).length === 0 ? (
          <p className="mt-3 text-sm text-red-500">{t("userMessages.validationSummary")}</p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border px-4 py-2 text-sm"
          >
            {t("common.cancel")}
          </button>
          <button
            disabled={mutation.isPending}
            className="rounded-xl bg-[var(--brand-primary)] px-4 py-2 text-sm font-bold text-white"
          >
            {mutation.isPending ? t("common.saving") : t("users.saveUser")}
          </button>
        </div>
      </form>
    </div>
  );
}
function UsersGrid() {
  const { t, formatDate } = useLocale();
  const roleLabel = (value) => { const system = t(`systemRoleNames.${value}`); if (!system.startsWith("systemRoleNames.")) return system; const translated = t(`roleNames.${value}`); return translated.startsWith("roleNames.") ? value : translated; };
  const departmentLabel = (value) => localizedCanonical(t, "departmentNames", value);
  const cache = useQueryClient();
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState([]);
  const [dialogUser, setDialogUser] = useState(undefined);
  const [toast, setToast] = useState("");
  const params = {
    page,
    page_size: 25,
    search,
    department,
    role,
    status,
    sort_by: "created_at",
    sort_direction: "desc",
  };
  const { data, isLoading, error } = useQuery({
    queryKey: ["identity-users", params],
    queryFn: () => api.identityUsers(params),
    placeholderData: (old) => old,
  });
  const { data: meta } = useQuery({
    queryKey: ["identity-meta"],
    queryFn: api.identityMeta,
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, active }) => api.setIdentityUserStatus(id, active),
    onMutate: async ({ id, active }) => {
      await cache.cancelQueries({ queryKey: ["identity-users"] });
      const old = cache.getQueryData(["identity-users", params]);
      cache.setQueryData(["identity-users", params], (current) =>
        current
          ? {
              ...current,
              items: current.items.map((u) =>
                u.id === id ? { ...u, is_active: active } : u,
              ),
            }
          : current,
      );
      return { old };
    },
    onError: (_, __, context) =>
      cache.setQueryData(["identity-users", params], context?.old),
    onSettled: () => cache.invalidateQueries({ queryKey: ["identity-users"] }),
  });
  const tempMutation = useMutation({
    mutationFn: api.generateIdentityTemporaryPassword,
    onSuccess: (result) =>
      setToast(t("userMessages.temporaryPassword", { password: result.temporary_password })),
  });
  const logoutMutation = useMutation({
    mutationFn: api.forceIdentityLogout,
    onSuccess: () => setToast(t("userMessages.sessionsRevoked")),
  });
  const users = data?.items || [];
  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / 25));
  const action = (fn, label) => {
    if (window.confirm(label)) fn();
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-4 shadow-sm xl:flex-row">
        <input
          className={`${input} min-w-0 flex-1`}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder={t("platformAdministration.searchUsers")}
        />
        <select
          className={input}
          value={department}
          onChange={(e) => {
            setDepartment(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{t("platformAdministration.allDepartments")}</option>
          {(meta?.departments || []).map((value) => (
            <option key={value} value={value}>{departmentLabel(value)}</option>
          ))}
        </select>
        <select
          className={input}
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{t("platformAdministration.allRoles")}</option>
          {(meta?.roles || []).map((value) => (
            <option key={value} value={value}>{roleLabel(value)}</option>
          ))}
        </select>
        <select
          className={input}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{t("platformAdministration.allStatuses")}</option><option value="active">{t("common.active")}</option><option value="inactive">{t("common.inactive")}</option>
        </select>
        <button
          onClick={() => setDialogUser(null)}
          className="rounded-xl bg-[var(--brand-primary)] px-4 py-2 text-sm font-bold text-white"
        >
          {t("platformAdministration.createUser")}
        </button>
      </div>
      {selected.length ? (
        <div className="flex items-center justify-between rounded-2xl bg-[var(--brand-secondary)] px-4 py-3 text-sm text-[var(--brand-primary)]">
          <strong>{selected.length} {t("platformAdministration.selected")}</strong>
          <div className="flex gap-2">
            <button
              onClick={() =>
                action(
                  () =>
                    selected.forEach((id) =>
                      statusMutation.mutate({ id, active: true }),
                    ),
                  t("userMessages.activateSelected"),
                )
              }
            >
              {t("platformAdministration.activate")}
            </button>
            <button
              onClick={() =>
                action(
                  () =>
                    selected.forEach((id) =>
                      statusMutation.mutate({ id, active: false }),
                    ),
                  t("userMessages.deactivateSelected"),
                )
              }
            >
              {t("platformAdministration.deactivate")}
            </button>
          </div>
        </div>
      ) : null}
      <section className="overflow-hidden rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] shadow-sm">
        {isLoading ? (
          <Skeleton />
        ) : error ? (
          <p className="p-6 text-red-500">{error.message}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-[1600px] w-full text-left text-sm">
              <thead className="bg-black/5 text-xs uppercase tracking-wide text-[var(--brand-muted)]">
                <tr>
                  <th className="p-3">
                    <input
                      type="checkbox"
                      checked={
                        users.length > 0 && selected.length === users.length
                      }
                      onChange={(e) =>
                        setSelected(
                          e.target.checked ? users.map((u) => u.id) : [],
                        )
                      }
                    />
                  </th>
                  {[
                    t("userTable.avatar"), t("users.fullName"), t("users.username"), t("users.employeeId"), t("users.department"), t("platformAdministration.role"), t("users.position"), t("users.phone"), t("users.email"), t("users.telegram"), t("common.status"), t("userTable.lastLogin"), t("platformAdministration.created"), t("common.actions"),
                  ].map((name) => (
                    <th key={name} className="p-3 font-bold">
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.id}
                    className="border-t border-[var(--brand-muted)]/15 hover:bg-black/[.025]"
                  >
                    <td className="p-3">
                      <input
                        type="checkbox"
                        checked={selected.includes(user.id)}
                        onChange={(e) =>
                          setSelected((old) =>
                            e.target.checked
                              ? [...old, user.id]
                              : old.filter((id) => id !== user.id),
                          )
                        }
                      />
                    </td>
                    <td className="p-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--brand-secondary)] text-xs font-bold text-[var(--brand-primary)]">
                        {(user.full_name || user.username)
                          .slice(0, 1)
                          .toUpperCase()}
                      </div>
                    </td>
                    <td className="p-3 font-semibold text-[var(--brand-text)]">
                      {user.full_name || "—"}
                    </td>
                    <td className="p-3">{user.username}</td>
                    <td className="p-3">{user.employee_id || "—"}</td>
                    <td className="p-3">{user.department ? departmentLabel(user.department) : "—"}</td>
                    <td className="p-3">{roleLabel(user.role)}</td>
                    <td className="p-3">{user.position || "—"}</td>
                    <td className="p-3">{user.phone || "—"}</td>
                    <td className="p-3">{user.email || "—"}</td>
                    <td className="p-3">{user.telegram || "—"}</td>
                    <td className="p-3">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-bold ${user.is_active ? "bg-emerald-500/15 text-emerald-700" : "bg-red-500/15 text-red-600"}`}
                      >
                        {t(user.is_active ? "common.active" : "common.inactive")}
                      </span>
                    </td>
                    <td className="p-3">
                      {user.last_login_at
                        ? formatDate(user.last_login_at, { dateStyle: "short", timeStyle: "short" }) : t("platformAdministration.never")}
                    </td>
                    <td className="p-3">
                      {user.created_at
                        ? formatDate(user.created_at, { dateStyle: "short" })
                        : "—"}
                    </td>
                    <td className="p-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setDialogUser(user)}
                          className="font-bold text-[var(--brand-primary)]"
                        >
                          {t("common.edit")}
                        </button>
                        <button
                          onClick={() =>
                            action(
                              () =>
                                statusMutation.mutate({
                                  id: user.id,
                                  active: !user.is_active,
                                }),
                              t("userMessages.changeStatus", { username: user.username, action: t(user.is_active ? "platformAdministration.deactivate" : "platformAdministration.activate") }),
                            )
                          }
                        >
                          {t(user.is_active ? "platformAdministration.deactivate" : "platformAdministration.activate")}
                        </button>
                        <button
                          onClick={() =>
                            action(
                              () => tempMutation.mutate(user.id),
                              t("userMessages.generatePassword", { username: user.username }),
                            )
                          }
                        >
                          {t("platformAdministration.temporaryPassword")}
                        </button>
                        <button
                          onClick={() =>
                            action(
                              () => logoutMutation.mutate(user.id),
                              t("userMessages.logoutConfirm", { username: user.username }),
                            )
                          }
                        >
                          {t("platformAdministration.forceLogout")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <footer className="flex items-center justify-between border-t border-[var(--brand-muted)]/15 px-4 py-3 text-sm text-[var(--brand-muted)]">
          <span>{data?.total || 0} {t("platformAdministration.usersCount")}</span>
          <div className="flex items-center gap-3">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              {t("platformAdministration.previous")}
            </button>
            <span>
              {t("platformAdministration.page")} {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("platformAdministration.next")}
            </button>
          </div>
        </footer>
      </section>
      {toast ? (
        <div className="rounded-2xl bg-[var(--brand-primary)] px-4 py-3 text-sm text-white">
          {toast}
        </div>
      ) : null}
      {dialogUser !== undefined ? (
        <UserDialog
          user={dialogUser}
          roleOptions={(meta?.role_options || (meta?.roles || []).map((key) => ({ key }))).map((item) => ({ ...item, label: roleLabel(item.key) }))}
          departments={meta?.departments || []}
          onClose={() => setDialogUser(undefined)}
        />
      ) : null}
    </div>
  );
}
function DepartmentsPanel() {
  const { t } = useLocale();
  const cache = useQueryClient();
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const query = useQuery({ queryKey: ["identity-departments"], queryFn: api.identityDepartments });
  const refresh = () => { cache.invalidateQueries({ queryKey: ["identity-departments"] }); cache.invalidateQueries({ queryKey: ["identity-meta"] }); };
  const create = useMutation({ mutationFn: api.createIdentityDepartment, onSuccess: () => { setName(""); setMessage(t("notifications.saved")); refresh(); } });
  const rename = async (item) => {
    const next = window.prompt(t("platformAdministration.departmentNamePrompt"), item.name);
    if (!next || next === item.name) return;
    try { await api.renameIdentityDepartment(item.name, { name: next }); setMessage(t("notifications.saved")); refresh(); } catch (error) { setMessage(error.message); }
  };
  const remove = async (item) => {
    if (!window.confirm(t("platformAdministration.deleteDepartmentConfirm", { name: item.name }))) return;
    try { await api.deleteIdentityDepartment(item.name); setMessage(t("notifications.saved")); refresh(); } catch (error) { setMessage(error.message); }
  };
  if (query.isLoading) return <Skeleton />;
  return <section className="space-y-4 rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-6 shadow-sm">
    <h3 className="text-xl font-black">{t("users.departments")}</h3>
    <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(event) => { event.preventDefault(); if (name.trim()) create.mutate({ name: name.trim() }); }}>
      <input className={`${input} flex-1`} value={name} onChange={(event) => setName(event.target.value)} placeholder={t("platformAdministration.departmentName")} />
      <button disabled={create.isPending || !name.trim()} className="rounded-xl bg-[var(--brand-primary)] px-4 py-2 font-bold text-white">{t("common.create")}</button>
    </form>
    {(query.error || create.error) ? <p className="text-sm text-red-600">{(query.error || create.error).message}</p> : null}
    {message ? <p className="text-sm text-[var(--brand-muted)]">{message}</p> : null}
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{(query.data?.items || []).map((item) => <article key={item.name} className="rounded-2xl border p-4">
      <strong>{item.name}</strong><p className="text-xs text-[var(--brand-muted)]">{item.user_count} {t("platformAdministration.usersCount")}</p>
      <div className="mt-3 flex gap-3 text-sm"><button disabled={item.is_system} onClick={() => rename(item)}>{t("common.edit")}</button><button disabled={item.is_system || item.user_count > 0} className="text-red-600 disabled:opacity-40" onClick={() => remove(item)}>{t("common.delete")}</button></div>
    </article>)}</div>
  </section>;
}

function ActivityPanel() {
  const { t, formatDate } = useLocale();
  const query = useQuery({ queryKey: ["identity-activity"], queryFn: api.identityActivity });
  if (query.isLoading) return <Skeleton />;
  return <section className="rounded-3xl border bg-[var(--brand-card)] p-6"><h3 className="mb-4 text-xl font-black">{t("users.activity")}</h3>
    {query.error ? <p className="text-red-600">{query.error.message}</p> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-sm"><thead><tr>{["actor","action","entity","time"].map((key) => <th className="p-3 text-left" key={key}>{t(`platformAdministration.activityColumns.${key}`)}</th>)}</tr></thead><tbody>{(query.data?.items || []).map((item) => <tr className="border-t" key={item.id}><td className="p-3">{item.actor}</td><td className="p-3">{item.action}</td><td className="p-3">{item.entity_type}{item.entity_id ? ` #${item.entity_id}` : ""}</td><td className="p-3">{formatDate(item.created_at, { dateStyle: "short", timeStyle: "short" })}</td></tr>)}</tbody></table></div>}
    {!query.error && !query.data?.items?.length ? <p className="text-sm text-[var(--brand-muted)]">{t("common.noData")}</p> : null}
  </section>;
}

function SessionsPanel() {
  const { t, formatDate } = useLocale();
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["identity-sessions"], queryFn: api.identitySessions });
  const revoke = useMutation({ mutationFn: api.revokeIdentitySession, onSuccess: () => cache.invalidateQueries({ queryKey: ["identity-sessions"] }) });
  if (query.isLoading) return <Skeleton />;
  return <section className="rounded-3xl border bg-[var(--brand-card)] p-6"><h3 className="mb-4 text-xl font-black">{t("users.sessions")}</h3>
    {(query.error || revoke.error) ? <p className="text-red-600">{(query.error || revoke.error).message}</p> : null}
    <div className="space-y-3">{(query.data?.items || []).map((session) => <article className="flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center" key={session.id}><div className="min-w-0 flex-1"><strong>{session.username}</strong><p className="truncate text-sm text-[var(--brand-muted)]">{session.device || session.browser || t("platformAdministration.unknownDevice")} · {formatDate(session.last_seen_at, { dateStyle: "short", timeStyle: "short" })}</p></div><span className="text-sm">{t(session.is_active ? "common.active" : "common.inactive")}</span>{session.is_active ? <button className="rounded-xl border px-3 py-2 text-sm" disabled={revoke.isPending} onClick={() => window.confirm(t("platformAdministration.revokeSessionConfirm")) && revoke.mutate(session.id)}>{t("platformAdministration.revokeSession")}</button> : null}</article>)}</div>
    {!query.data?.items?.length ? <p className="text-sm text-[var(--brand-muted)]">{t("platformAdministration.noSessions")}</p> : null}
  </section>;
}
function EnterpriseUsers() {
  const { t } = useLocale();
  const [tab, setTab] = useState("users");
  return (
    <div className="space-y-5">
      <header className="rounded-3xl border border-[var(--brand-muted)]/20 bg-[var(--brand-card)] p-6 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[.18em] text-[var(--brand-muted)]">
          {t("platformAdministration.identityAccess")}
        </p>
        <h2 className="mt-1 text-2xl font-black text-[var(--brand-text)]">
          {t("platformAdministration.userManagement")}
        </h2>
        <p className="mt-2 text-sm text-[var(--brand-muted)]">
          {t("platformAdministration.userManagementDescription")}
        </p>
      </header>
      <nav className="flex gap-2 overflow-x-auto pb-1">
        {sections.map((name) => (
          <button
            key={name}
            onClick={() => setTab(name)}
            className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-bold ${tab === name ? "bg-[var(--brand-secondary)] text-[var(--brand-primary)]" : "bg-[var(--brand-card)] text-[var(--brand-muted)]"}`}
          >
            {t(`users.${name}`)}
          </button>
        ))}
      </nav>
      {tab === "users" ? (
        <UsersGrid />
      ) : tab === "roles" ? <RolesTab />
        : tab === "departments" ? <DepartmentsPanel />
          : tab === "activity" ? <ActivityPanel />
            : tab === "sessions" ? <SessionsPanel />
              : <SecurityTab />}
    </div>
  );
}
export default function UsersTab() {
  return (
    <QueryClientProvider client={queryClient}>
      <EnterpriseUsers />
    </QueryClientProvider>
  );
}
