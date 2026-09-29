const IDENTITY_FIELDS = [
  "username", "role", "department", "full_name", "employee_id", "position",
  "phone", "email", "telegram", "avatar_url",
];

export function normalizeUserIdentityDefaults(user) {
  if (!user) return { role: "operator", is_active: true, department: "", password: "" };
  return Object.fromEntries(
    Object.entries({ ...user, password: "" }).map(([key, value]) => [key, value ?? ""]),
  );
}

export function buildUserIdentityPayload(data, { passwordIntent = false, passwordDirty = false } = {}) {
  const payload = Object.fromEntries(IDENTITY_FIELDS.map((key) => [key, data?.[key] ?? ""]));
  payload.is_active = Boolean(data?.is_active);
  const password = typeof data?.password === "string" ? data.password.trim() : "";
  if (passwordIntent && passwordDirty && password) payload.password = password;
  return payload;
}
