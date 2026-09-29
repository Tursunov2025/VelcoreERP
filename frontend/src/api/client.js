const CONFIGURED_API_URL = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");
export { normalizeApiErrorPayload } from "./errorNormalizer.js";
import { normalizeApiErrorPayload } from "./errorNormalizer.js";

if (!CONFIGURED_API_URL) {
  throw new Error("VITE_API_URL is required. Select the correct Vite mode/environment file.");
}

/** Runtime override when build was compiled with wrong VITE_API_URL (VPS hostname). */
export function productionApiUrlFromHost() {
  return CONFIGURED_API_URL;
}

function resolveBuiltInApiUrl() {
  return CONFIGURED_API_URL;
}

let API_BASE = resolveBuiltInApiUrl();

let apiConfigPromise = null;

/** Load /remote-api.json only for local dev вЂ” never override Velcore production API URL. */
async function ensureApiBase() {
  if (apiConfigPromise) return apiConfigPromise;
  apiConfigPromise = (async () => {
    if (import.meta.env.VITE_RUNTIME_API_CONFIG !== "true") {
      return API_BASE;
    }

    try {
      const res = await fetch(`/remote-api.json?_=${Date.now()}`, { cache: "no-store" });
      if (res.ok) {
        const cfg = await res.json();
        if (cfg?.apiUrl) {
          API_BASE = String(cfg.apiUrl).replace(/\/+$/, "");
        }
      }
    } catch {
      /* use build-time default */
    }
    if (import.meta.env.DEV) {
      console.info(`[api] base URL = ${API_BASE}`);
    }
    return API_BASE;
  })();
  return apiConfigPromise;
}

export function getApiBase() {
  return API_BASE;
}

/** Always call before raw fetch() outside request(). */
export async function getResolvedApiBase() {
  await ensureApiBase();
  return getApiBase();
}

export async function authenticatedFetch(path, options = {}) {
  await ensureApiBase();
  const tokens = getStoredTokens();
  const headers = { ...options.headers };
  if (tokens?.access_token) {
    headers.Authorization = `Bearer ${tokens.access_token}`;
  }
  const url = path.startsWith("http") ? path : `${getApiBase()}${path}`;
  return fetch(url, { ...options, headers });
}

const TOKEN_KEY = "azmus_tokens";

export function getStoredTokens() {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredTokens(tokens) {
  if (tokens) {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

let refreshPromise = null;

async function refreshAccessToken() {
  await ensureApiBase();
  const tokens = getStoredTokens();
  if (!tokens?.refresh_token) return null;

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Refresh failed");
        const data = await res.json();
        setStoredTokens({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          username: data.username,
          role: data.role,
          department: data.department,
        });
        return data.access_token;
      })
      .catch(() => {
        setStoredTokens(null);
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function request(path, options = {}, retry = true) {
  await ensureApiBase();
  const tokens = getStoredTokens();
  const headers = { ...options.headers };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (tokens?.access_token) {
    headers.Authorization = `Bearer ${tokens.access_token}`;
  }

  const method = options.method || "GET";
  const url = `${getApiBase()}${path}`;

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (networkErr) {
    const cancelled = networkErr?.name === "AbortError" || options.signal?.aborted;
    const error = new Error(cancelled ? "Request cancelled" : "Network request failed");
    error.code = cancelled ? "request_cancelled" : "network_error";
    error.cause = networkErr;
    throw error;
  }

  if (response.status === 401 && retry && tokens?.refresh_token) {
    const newToken = await refreshAccessToken();
    if (newToken) return request(path, options, false);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const normalized = normalizeApiErrorPayload(data, response.statusText || "Request failed");

    if (response.status === 401) {
      setStoredTokens(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }

    if (response.status === 404) {
      console.error(
        `[api] ${method} ${url} в†’ 404 Not Found. ` +
          `Tekshiring: VITE_API_URL (${API_BASE}) shu route mavjud bo'lgan backendga ishora qilyaptimi?`
      );
    } else {
      console.error(`[api] ${method} ${url} в†’ ${response.status}`, data);
    }

    const error = new Error(normalized.message);
    error.status = response.status;
    error.data = data;
    error.code = normalized.code;
    error.fieldErrors = normalized.fieldErrors;
    throw error;
  }

  if (data?.error) throw new Error(data.error);
  return data;
}

export function uploadUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${getApiBase()}${path}`;
}

export const api = {
  identityUsers: (params = {}) => request(`/admin/identity/users?${new URLSearchParams(params).toString()}`),
  identityMeta: () => request("/admin/identity/meta"),
  identityDepartments: () => request("/admin/identity/departments"),
  createIdentityDepartment: (body) => request("/admin/identity/departments", { method: "POST", body: JSON.stringify(body) }),
  renameIdentityDepartment: (name, body) => request(`/admin/identity/departments/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteIdentityDepartment: (name) => request(`/admin/identity/departments/${encodeURIComponent(name)}`, { method: "DELETE" }),
  identityActivity: () => request("/admin/identity/activity"),
  identitySessions: () => request("/admin/identity/sessions"),
  revokeIdentitySession: (id) => request(`/admin/identity/sessions/${id}/revoke`, { method: "POST" }),
  createIdentityUser: (body) => request("/admin/identity/users", { method: "POST", body: JSON.stringify(body) }),
  updateIdentityUser: (id, body) => request(`/admin/identity/users/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  setIdentityUserStatus: (id, active) => request(`/admin/identity/users/${id}/status?active=${active}`, { method: "POST" }),
  generateIdentityTemporaryPassword: (id) => request(`/admin/identity/users/${id}/temporary-password`, { method: "POST" }),
  forceIdentityLogout: (id) => request(`/admin/identity/users/${id}/force-logout`, { method: "POST" }),
  identityUserActivity: (id) => request(`/admin/identity/users/${id}/activity`),
  organizationSettings: () => request("/admin/organization"),
  updateOrganizationSettings: (body) =>
    request("/admin/organization", { method: "PUT", body: JSON.stringify(body) }),
  uploadOrganizationAsset: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/admin/organization/assets", { method: "POST", body: form });
  },
  platformAccess: () => request("/admin/platform/access"),
  platformRoles: () => request("/admin/platform/roles"),
  platformCreateRole: (body) => request("/admin/platform/roles", { method: "POST", body: JSON.stringify(body) }),
  platformUpdateRole: (id, body) => request(`/admin/platform/roles/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  platformDeleteRole: (id) => request(`/admin/platform/roles/${id}`, { method: "DELETE" }),
  platformAppearance: () => request("/admin/platform/appearance"),
  platformSaveAppearance: (body) => request("/admin/platform/appearance", { method: "PUT", body: JSON.stringify(body) }),
  platformResetAppearance: () => request("/admin/platform/appearance/reset", { method: "POST" }),
  platformUploadLogo: (file) => { const body = new FormData(); body.append("file", file); return request("/admin/platform/appearance/logo", { method: "POST", body }); },
  platformRemoveLogo: () => request("/admin/platform/appearance/logo", { method: "DELETE" }),
  platformNavigation: () => request("/admin/platform/navigation"),
  platformSaveNavigation: (id, body) => request(`/admin/platform/navigation/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  platformResetNavigation: () => request("/admin/platform/navigation/reset", { method: "POST" }),
  platformModules: () => request("/admin/platform/modules"),
  platformSaveModule: (key, body) => request(`/admin/platform/modules/${key}`, { method: "PUT", body: JSON.stringify(body) }),
  platformIntegrations: () => request("/admin/platform/integrations"),
  platformTestTelegram: () => request("/admin/platform/integrations/telegram/test", { method: "POST" }),
  platformBackups: () => request("/admin/platform/backups"),
  platformCreateBackup: () => request("/admin/platform/backups", { method: "POST" }),
  platformBackupPreflight: (name) => request(`/admin/platform/backups/${encodeURIComponent(name)}/preflight`, { method: "POST" }),
  platformBackupDownloadUrl: (name) => `${API_BASE}/admin/platform/backups/${encodeURIComponent(name)}/download`,
  platformAudit: (params = {}) => request(`/admin/platform/audit?${new URLSearchParams(params).toString()}`),
  platformAuditCsvUrl: () => `${API_BASE}/admin/platform/audit/export.csv`,
  platformSecurity: () => request("/admin/platform/security"),
  platformSaveSecurity: (body) => request("/admin/platform/security", { method: "PUT", body: JSON.stringify(body) }),
  platformSystem: () => request("/admin/platform/system"),
  platformAbout: () => request("/admin/platform/about"),
  // Display Center вЂ” isolated enterprise signage API
  displayDashboard: () => request("/display-center/dashboard"),
  displayFactoryDashboard: () => request("/display-center/factory-dashboard"),
  displayRuntime: (code) => request(`/display-center/display/${encodeURIComponent(code)}`),
  displayTemplate: (id) => request(`/display-center/templates/${id}`),
  displayTemplates: () => request("/display-center/templates"),
  createDisplayTemplate: (body) => request("/display-center/templates", { method: "POST", body: JSON.stringify(body) }),
  updateDisplayTemplate: (id, body) => request(`/display-center/templates/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  cloneDisplayTemplate: (id, body = {}) => request(`/display-center/templates/${id}/clone`, { method: "POST", body: JSON.stringify(body) }),
  deleteDisplayTemplate: (id) => request(`/display-center/templates/${id}`, { method: "DELETE" }),
  displayHeartbeat: (body) => request("/display-center/heartbeat", { method: "POST", body: JSON.stringify(body) }),
  displayMeta: () => request("/display-center/meta"),
  displays: () => request("/display-center/displays"),
  createDisplay: (body) => request("/display-center/displays", { method: "POST", body: JSON.stringify(body) }),
  updateDisplay: (id, body) => request(`/display-center/displays/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDisplay: (id) => request(`/display-center/displays/${id}`, { method: "DELETE" }),
  displayWidgets: () => request("/display-center/widgets"),
  createDisplayWidget: (body) => request("/display-center/widgets", { method: "POST", body: JSON.stringify(body) }),
  updateDisplayWidget: (id, body) => request(`/display-center/widgets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDisplayWidget: (id) => request(`/display-center/widgets/${id}`, { method: "DELETE" }),
  displayPlaylists: () => request("/display-center/playlists"),
  createDisplayPlaylist: (body) => request("/display-center/playlists", { method: "POST", body: JSON.stringify(body) }),
  updateDisplayPlaylist: (id, body) => request(`/display-center/playlists/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDisplayPlaylist: (id) => request(`/display-center/playlists/${id}`, { method: "DELETE" }),
  displayPlaylistItems: (id) => request(`/display-center/playlists/${id}/items`),
  createDisplayPlaylistItem: (id, body) => request(`/display-center/playlists/${id}/items`, { method: "POST", body: JSON.stringify(body) }),
  updateDisplayPlaylistItem: (id, body) => request(`/display-center/playlist-items/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDisplayPlaylistItem: (id) => request(`/display-center/playlist-items/${id}`, { method: "DELETE" }),
  displaySchedules: () => request("/display-center/schedules"),
  createDisplaySchedule: (body) => request("/display-center/schedules", { method: "POST", body: JSON.stringify(body) }),
  updateDisplaySchedule: (id, body) => request(`/display-center/schedules/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDisplaySchedule: (id) => request(`/display-center/schedules/${id}`, { method: "DELETE" }),
  displayMonitoring: () => request("/display-center/monitoring"),
  displaySettings: () => request("/display-center/settings"),
  saveDisplaySettings: (body) => request("/display-center/settings", { method: "PUT", body: JSON.stringify(body) }),
  displayMedia: (q = "") => request(`/display-center/media${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  uploadDisplayMedia: (file, folderId = null) => { const form = new FormData(); form.append("file", file); return request(`/display-center/media/upload${folderId ? `?folder_id=${folderId}` : ""}`, { method: "POST", body: form }); },
  deleteDisplayMedia: (id) => request(`/display-center/media/${id}`, { method: "DELETE" }),
  traceabilityDashboard: () => request("/traceability/dashboard"),
  traceabilityProducts: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== "" && v !== null && v !== undefined && v !== false) q.set(k, String(v)); });
    return request(`/traceability/products${q.toString() ? `?${q.toString()}` : ""}`);
  },
  traceabilityProduct: (serial) => request(`/traceability/products/${encodeURIComponent(serial)}`),
  generateProductPassports: (packageId) => request(`/traceability/packages/${packageId}/passports`, { method: "POST" }),
  generateProductPassportsBatch: (packageIds) => request("/traceability/passports/batch", { method: "POST", body: JSON.stringify({ package_ids: packageIds }) }),
  productPassportLabelUrl: (serial, size = "100x50") => `${API_BASE}/traceability/products/${encodeURIComponent(serial)}/label.png?size=${encodeURIComponent(size)}`,
  productPassportPdfUrl: (serial) => `${API_BASE}/traceability/products/${encodeURIComponent(serial)}/label.pdf`,
  productPassportDocumentUrl: (serial, format, language = "uz") => `${API_BASE}/traceability/products/${encodeURIComponent(serial)}/passport.${encodeURIComponent(format)}?language=${encodeURIComponent(language)}`,
  traceabilityBatchLabelPdfUrl: () => `${API_BASE}/traceability/passports/batch/labels.pdf`,
  traceabilityBatchExcelUrl: () => `${API_BASE}/traceability/passports/batch/export.xlsx`,
  publicProductPassport: (token) => request(`/track/product/${encodeURIComponent(token)}`),
  login: async (body) => {
    await ensureApiBase();
    const url = `${getApiBase()}/auth/login`;
    let res;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (networkErr) {
      // Never log credentials; URL and the platform error are enough to diagnose APK networking.
      console.error(`[api] POST ${url} вЂ” login network error:`, networkErr);
      throw new Error(
        `Login tarmoq xatosi: ${networkErr?.message || "noma'lum xato"}. URL: ${url}`
      );
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      console.error(`[api] POST ${url} в†’ ${res.status} ${res.statusText}`, data);
      const detail =
        data?.error ||
        data?.detail ||
        (Array.isArray(data?.detail) ? data.detail[0]?.msg : null) ||
        res.statusText ||
        "Login failed";
      throw new Error(`Login xatosi (HTTP ${res.status}): ${detail}`);
    }
    return data;
  },

  getMe: () => request("/auth/me"),
  getUsers: () => request("/users"),
  getLoginUsers: () => request("/auth/login-users"),
  createUser: (body) =>
    request("/users", { method: "POST", body: JSON.stringify(body) }),

  getOrders: () => request("/orders"),
  getOrder: (id) => request(`/orders/${id}`),
  getKanban: () => request("/orders/kanban"),
  createOrder: (body) =>
    request("/orders", { method: "POST", body: JSON.stringify(body) }),
  updateOrder: (id, body) =>
    request(`/orders/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  completeOrder: (id, body) =>
    request(`/orders/${id}/complete`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  verifyOrder: (id, body) =>
    request(`/orders/${id}/verify`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getOrderHistory: (id) => request(`/orders/${id}/history`),
  deleteOrder: (id) => request(`/orders/${id}`, { method: "DELETE" }),

  getReadyWarehouse: (q = "") =>
    request(`/warehouse/ready${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getMaterials: () => request("/warehouse/materials"),
  createMaterial: (body) =>
    request("/warehouse/materials", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getStockAlerts: () => request("/warehouse/alerts"),
  stockMovement: (body) =>
    request("/warehouse/movements", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  dispatchShipment: (body) =>
    request("/shipping/dispatch", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getShippingArchive: () => request("/shipping/archive"),
  getShipmentGroups: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) {
        q.set(k, String(v));
      }
    });
    return request(`/shipping/groups?${q.toString()}`);
  },
  getShipmentGroup: (id) => request(`/shipping/groups/${id}`),
  adminDeleteShipmentGroup: (id) =>
    request(`/shipping/groups/${id}`, { method: "DELETE" }),
  adminRestoreShipmentGroup: (id) =>
    request(`/shipping/groups/${id}/restore`, { method: "POST" }),

  getChatRooms: () => request("/chat/rooms"),
  getChatMessages: (roomId, sinceId = 0) =>
    request(
      `/chat/rooms/${roomId}/messages${sinceId ? `?since_id=${sinceId}` : ""}`
    ),
  sendChatMessage: (roomId, body) =>
    request(`/chat/rooms/${roomId}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  markChatRead: (roomId) =>
    request(`/chat/rooms/${roomId}/read`, { method: "POST" }),
  getChatUnread: () => request("/chat/unread"),
  createPrivateChat: (username) =>
    request("/chat/private", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),
  setChatTyping: (roomId, isTyping = true) =>
    request("/chat/typing", {
      method: "POST",
      body: JSON.stringify({ room_id: roomId, is_typing: isTyping }),
    }),
  getChatTyping: (roomId) => request(`/chat/typing/${roomId}`),
  getChatOnline: () => request("/chat/online"),
  getChatUsers: () => request("/chat/users"),
  uploadChatFile: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const data = await request("/uploads/file", { method: "POST", body: form });
    return { ...data, url: data.url };
  },
  uploadAnyFile: async (file) => {
    const form = new FormData();
    form.append("file", file, file.name);
    if (import.meta.env.DEV) {
      console.info("[upload] POST /uploads/file", {
        name: file.name,
        type: file.type,
        size: file.size,
      });
    }
    const data = await request("/uploads/file", { method: "POST", body: form });
    const result = {
      url: data.url,
      filename: data.original_filename || data.filename || file.name,
      content_type: data.content_type || file.type || "",
    };
    if (import.meta.env.DEV) {
      console.info("[upload] ok", result);
    }
    return result;
  },

  getTasks: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) {
        q.set(k, String(v));
      }
    });
    const qs = q.toString();
    return request(`/tasks${qs ? `?${qs}` : ""}`);
  },
  getTask: (id) => request(`/tasks/${id}`),
  getTaskStats: () => request("/tasks/stats"),
  createTask: (body) =>
    request("/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id, body) =>
    request(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: "DELETE" }),
  archiveTask: (id) =>
    request(`/tasks/${id}/archive`, { method: "POST" }),
  changeTaskStatus: (assignmentId, body) =>
    request(`/task-assignments/${assignmentId}/status`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTaskComments: (taskId) =>
    request(`/task-comments?task_id=${taskId}`),
  addTaskComment: (body) =>
    request("/task-comments", { method: "POST", body: JSON.stringify(body) }),
  getTaskAttachments: (taskId) =>
    request(`/task-attachments?task_id=${taskId}`),
  addTaskAttachment: (body) =>
    request("/task-attachments", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getProductionTimeline: (orderId) =>
    request(`/production/timeline/${orderId}`),
  getProductionAnalytics: () => request("/production/analytics"),

  getOnlineOperators: () => request("/operators/online"),
  getOperatorStats: () => request("/operators/stats"),
  getDashboardAnalytics: () => request("/analytics/dashboard"),

  getFinanceSummary: () => request("/finance/summary"),
  getFinanceRecords: () => request("/finance/records"),
  addExpense: (body) =>
    request("/finance/expenses", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  addIncome: (body) =>
    request("/finance/income", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  uploadImage: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const data = await request("/uploads/image", { method: "POST", body: form });
    return { ...data, url: uploadUrl(data.url) };
  },

  adminGetUsers: () => request("/admin/users"),
  adminCreateUser: (body) =>
    request("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  adminUpdateUser: (id, body) =>
    request(`/admin/users/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  adminDeleteUser: (id) => request(`/admin/users/${id}`, { method: "DELETE" }),
  adminResetPassword: (id, body) =>
    request(`/admin/users/${id}/reset-password`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  adminSearchOrders: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) {
        q.set(k, String(v));
      }
    });
    return request(`/admin/orders/search?${q.toString()}`);
  },
  adminUpdateOrder: (id, body) =>
    request(`/admin/orders/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  adminDeleteOrder: (id) => request(`/admin/orders/${id}`, { method: "DELETE" }),
  adminRestoreOrder: (id) =>
    request(`/admin/orders/${id}/restore`, { method: "POST" }),

  adminGetSystemSettings: () => request("/admin/settings/system"),
  adminUpdateSystemSettings: (body) =>
    request("/admin/settings/system", { method: "PUT", body: JSON.stringify(body) }),
  adminGetCompanySettings: () => request("/admin/settings/company"),
  adminUpdateCompanySettings: (body) =>
    request("/admin/settings/company", { method: "PUT", body: JSON.stringify(body) }),
  adminGetProductionSettings: () => request("/admin/settings/production"),
  adminUpdateProductionSettings: (body) =>
    request("/admin/settings/production", { method: "PUT", body: JSON.stringify(body) }),
  adminGetWarehouseSettings: () => request("/admin/settings/warehouse"),
  adminUpdateWarehouseSettings: (body) =>
    request("/admin/settings/warehouse", { method: "PUT", body: JSON.stringify(body) }),
  adminGetMaterialsSettings: () => request("/admin/settings/materials"),
  adminUpdateMaterialsSettings: (body) =>
    request("/admin/settings/materials", { method: "PUT", body: JSON.stringify(body) }),
  adminGetCostingSettings: () => request("/admin/settings/costing"),
  adminUpdateCostingSettings: (body) =>
    request("/admin/settings/costing", { method: "PUT", body: JSON.stringify(body) }),
  adminGetBackupSettings: () => request("/admin/settings/backup"),
  adminUpdateBackupSettings: (body) =>
    request("/admin/settings/backup", { method: "PUT", body: JSON.stringify(body) }),
  adminExportSettings: (includeBranding = true) =>
    request(`/admin/settings/export?include_branding=${includeBranding ? "true" : "false"}`),
  adminImportSettings: (body) =>
    request("/admin/settings/import", { method: "POST", body: JSON.stringify(body) }),

  adminGetOnlineUsers: () => request("/admin/operators/online"),
  adminGetAuditLogs: (params = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.q) q.set("q", params.q);
    if (params.action) q.set("action", params.action);
    if (params.entity_type) q.set("entity_type", params.entity_type);
    if (params.username) q.set("username", params.username);
    const qs = q.toString();
    return request(`/admin/audit-logs${qs ? `?${qs}` : ""}`);
  },

  adminGetExecutiveSettings: () => request("/admin/settings/executive"),
  adminUpdateExecutiveSettings: (body) =>
    request("/admin/settings/executive", { method: "PUT", body: JSON.stringify(body) }),

  getMobileVersion: () => request("/mobile/version"),
  adminGetMobileVersions: () => request("/admin/mobile/versions"),
  adminGetLatestMobileVersion: () => request("/admin/mobile/versions/latest"),
  adminPublishMobileVersion: (body) =>
    request("/admin/mobile/versions/publish", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  adminUploadMobileApk: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/admin/mobile/apk-upload", { method: "POST", body: form });
  },

  getUiConfig: () => request("/control-center/config/ui"),

  superAdminConfig: () => request("/super-admin/config"),
  superAdminUpdateNav: (id, body) =>
    request(`/super-admin/navigation/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  superAdminCreateNav: (body) =>
    request("/super-admin/navigation", { method: "POST", body: JSON.stringify(body) }),
  superAdminDeleteNav: (id) => request(`/super-admin/navigation/${id}`, { method: "DELETE" }),
  superAdminReorderNav: (order) =>
    request("/super-admin/navigation/reorder", { method: "PUT", body: JSON.stringify(order) }),
  superAdminUpdateModule: (id, body) =>
    request(`/super-admin/modules/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  superAdminUpsertWidget: (body) =>
    request("/super-admin/widgets", { method: "POST", body: JSON.stringify(body) }),
  superAdminDeleteWidget: (key) => request(`/super-admin/widgets/${key}`, { method: "DELETE" }),
  superAdminCreateTheme: (body) =>
    request("/super-admin/themes", { method: "POST", body: JSON.stringify(body) }),
  superAdminUpdateTheme: (id, body) =>
    request(`/super-admin/themes/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  superAdminActivateTheme: (id) =>
    request(`/super-admin/themes/${id}/activate`, { method: "POST" }),
  superAdminGetForms: () => request("/super-admin/forms"),
  superAdminSaveForms: (forms) =>
    request("/super-admin/forms", { method: "PUT", body: JSON.stringify(forms) }),
  superAdminGetTables: () => request("/super-admin/tables"),
  superAdminSaveTables: (tables) =>
    request("/super-admin/tables", { method: "PUT", body: JSON.stringify(tables) }),
  superAdminUpdateRolePermissions: (roleId, body) =>
    request(`/super-admin/roles/${roleId}/permissions`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  superAdminAuditLogs: (params = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.entity_type) q.set("entity_type", params.entity_type);
    const qs = q.toString();
    return request(`/super-admin/audit-logs${qs ? `?${qs}` : ""}`);
  },
  superAdminSnapshot: (label = "") =>
    request("/super-admin/snapshot", { method: "POST", body: JSON.stringify({ label }) }),
  superAdminRollback: (versionId) =>
    request(`/super-admin/rollback/${versionId}`, { method: "POST" }),
  controlCenterOrders: (params = {}) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.customer) q.set("customer", params.customer);
    if (params.status) q.set("status", params.status);
    if (params.type) q.set("type", params.type);
    if (params.delayed_only) q.set("delayed_only", "true");
    return request(`/control-center/orders?${q.toString()}`);
  },

  adminImportBackup: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/admin/backup/import", { method: "POST", body: form });
  },

  getMyPermissions: () => request("/auth/me/permissions"),
  mesMyBrigadeTerminalAccess: () => request("/mes/brigades/my-access"),

  adminGetPermissions: () => request("/admin/permissions"),
  adminUpdateUserPermissions: (userId, body) =>
    request(`/admin/permissions/${userId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  adminGetTelegramSettings: () => request("/admin/settings/telegram"),
  adminUpdateTelegramSettings: (body) =>
    request("/admin/settings/telegram", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  adminTestTelegram: () =>
    request("/admin/settings/telegram/test", { method: "POST" }),

  adminGetNotificationSettings: () => request("/admin/settings/notifications"),
  adminUpdateNotificationSettings: (body) =>
    request("/admin/settings/notifications", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getBranding: () => request("/branding"),
  adminGetBranding: () => request("/admin/settings/branding"),
  adminUpdateBranding: (body) =>
    request("/admin/settings/branding", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  adminResetBranding: () =>
    request("/admin/settings/branding/reset", { method: "POST" }),
  uploadBrandingAsset: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/uploads/branding", { method: "POST", body: form });
  },

  getUiPreferences: () => request("/auth/me/ui-preferences"),
  updateUiPreferences: (body) =>
    request("/auth/me/ui-preferences", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  llpGetFolders: () => request("/llp/folders"),
  llpCreateFolder: (body) =>
    request("/llp/folders", { method: "POST", body: JSON.stringify(body) }),
  llpUpdateFolder: (id, body) =>
    request(`/llp/folders/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  llpDeleteFolder: (id) => request(`/llp/folders/${id}`, { method: "DELETE" }),
  llpGetDocuments: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/llp/documents?${q.toString()}`);
  },
  llpUploadDocument: async (file, { title, description, folder_id, is_important }) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    if (description) form.append("description", description);
    if (folder_id != null && folder_id !== "") form.append("folder_id", String(folder_id));
    form.append("is_important", is_important ? "true" : "false");
    return request("/llp/documents", { method: "POST", body: form });
  },
  llpUpdateDocument: (id, body) =>
    request(`/llp/documents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  llpDeleteDocument: (id) => request(`/llp/documents/${id}`, { method: "DELETE" }),
  llpMarkRead: (id) => request(`/llp/documents/${id}/read`, { method: "POST" }),

  // Logistics вЂ” finished warehouse + loading shipments
  logisticsDashboard: () => request("/logistics/dashboard"),
  logisticsProducts: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v != null) q.set(k, String(v));
    });
    const qs = q.toString();
    return request(`/logistics/products${qs ? `?${qs}` : ""}`);
  },
  logisticsCreateProduct: (body) =>
    request("/logistics/products", { method: "POST", body: JSON.stringify(body) }),
  logisticsUpdateProduct: (id, body) =>
    request(`/logistics/products/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  logisticsShipments: (status = "") =>
    request(status ? `/logistics/shipments?status=${encodeURIComponent(status)}` : "/logistics/shipments"),
  logisticsShipment: (id) => request(`/logistics/shipments/${id}`),
  logisticsCreateShipment: (body) =>
    request("/logistics/shipments", { method: "POST", body: JSON.stringify(body) }),
  logisticsAddShipmentItem: (shipmentId, body) =>
    request(`/logistics/shipments/${shipmentId}/items`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  logisticsLoadingScan: (body) =>
    request("/logistics/loading/scan", { method: "POST", body: JSON.stringify(body) }),
  logisticsDepartShipment: (id) =>
    request(`/logistics/shipments/${id}/depart`, { method: "POST" }),
  logisticsDeliverShipment: (id) =>
    request(`/logistics/shipments/${id}/deliver`, { method: "POST" }),

  // Phase 11B вЂ” Multi Currency
  currencies: () => request("/currencies"),
  currencyDashboard: () => request("/currencies/dashboard"),
  currencyRateHistory: (code, limit = 60) =>
    request(`/currencies/rates/history?currency_code=${encodeURIComponent(code)}&limit=${limit}`),
  addCurrencyRate: (body) =>
    request("/currencies/rates", { method: "POST", body: JSON.stringify(body) }),
  convertCurrency: (amount, from, to) =>
    request(`/currencies/convert?amount=${amount}&from=${from}&to=${to}`),

  // Phase 11B вЂ” Transport Management
  transports: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    const qs = q.toString();
    return request(`/transports${qs ? `?${qs}` : ""}`);
  },
  transportDashboard: () => request("/transports/dashboard"),
  transport: (id) => request(`/transports/${id}`),
  createTransport: (body) =>
    request("/transports", { method: "POST", body: JSON.stringify(body) }),
  updateTransport: (id, body) =>
    request(`/transports/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  updateTransportStatus: (id, status, comment = "") =>
    request(`/transports/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, comment }),
    }),

  // Phase 11B вЂ” CRM / Customer debt
  crmLedger: (q = "") => request(`/crm/ledger${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  crmTopDebtors: (limit = 5) => request(`/crm/top-debtors?limit=${limit}`),
  crmPayments: (customer = "") =>
    request(`/crm/payments${customer ? `?customer=${encodeURIComponent(customer)}` : ""}`),
  crmRecordPayment: (body) =>
    request("/crm/payments", { method: "POST", body: JSON.stringify(body) }),

  // Phase 11B вЂ” Dashboard KPIs + Warehouse forecast
  dashboardKpis: () => request("/dashboard/kpis"),
  warehouseForecast: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    const qs = q.toString();
    return request(`/warehouse-forecast/${qs ? `?${qs}` : ""}`);
  },
  warehouseForecastAlerts: (limit = 8) => request(`/warehouse-forecast/alerts?limit=${limit}`),

  // Phase 12 вЂ” GPS Fleet Tracking
  gpsVehicles: () => request("/gps/vehicles"),
  gpsCreateVehicle: (body) =>
    request("/gps/vehicles", { method: "POST", body: JSON.stringify(body) }),
  gpsDrivers: () => request("/gps/drivers"),
  gpsCreateDriver: (body) =>
    request("/gps/drivers", { method: "POST", body: JSON.stringify(body) }),
  gpsUpdateLocation: (body) =>
    request("/gps/location/update", { method: "POST", body: JSON.stringify(body) }),
  gpsUpdate: (body) =>
    request("/gps/update", { method: "POST", body: JSON.stringify(body) }),
  gpsLatestLocations: (vehicleId = null) =>
    request(
      vehicleId
        ? `/gps/location/latest?vehicle_id=${vehicleId}`
        : "/gps/location/latest"
    ),
  gpsLive: (vehicleId = null) =>
    request(vehicleId ? `/gps/live?vehicle_id=${vehicleId}` : "/gps/live"),
  gpsLocationHistory: (vehicleId, limit = 100) =>
    request(`/gps/location/history?vehicle_id=${vehicleId}&limit=${limit}`),
  gpsHistory: (vehicleId, limit = 100) =>
    request(`/gps/history/${vehicleId}?limit=${limit}`),
  gpsTransportTasks: (status = "") =>
    request(status ? `/gps/tasks?status=${encodeURIComponent(status)}` : "/gps/tasks"),
  gpsCreateTransportTask: (body) =>
    request("/gps/tasks", { method: "POST", body: JSON.stringify(body) }),
  gpsUpdateTransportTask: (id, body) =>
    request(`/gps/tasks/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  gpsStartTransportTask: (id) =>
    request(`/gps/tasks/${id}/start`, { method: "POST" }),
  gpsStopTransportTask: (id) =>
    request(`/gps/tasks/${id}/stop`, { method: "POST" }),
  gpsTrips: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    const qs = q.toString();
    return request(`/gps/trips${qs ? `?${qs}` : ""}`);
  },
  gpsCreateTrip: (body) =>
    request("/gps/trips", { method: "POST", body: JSON.stringify(body) }),
  gpsDashboard: () => request("/gps/dashboard"),

  // Professional GPS monitoring
  gpsTrackingFleet: (vehicleId = null) => {
    const query = vehicleId ? `?vehicle_id=${encodeURIComponent(vehicleId)}` : "";
    return request(`/mes/finished-logistics/tracking/fleet${query}`);
  },

  gpsTrackingHistory: (vehicleId, from, to) =>
    request(
      `/mes/finished-logistics/tracking/history?vehicle_id=${encodeURIComponent(vehicleId)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
    ),

  gpsTrackingHistoryDaily: (vehicleId, fromDate, toDate) =>
    request(
      `/mes/finished-logistics/tracking/history/daily?vehicle_id=${encodeURIComponent(vehicleId)}&from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`
    ),

  gpsTrackingHistoryStops: (vehicleId, from, to, minStopSeconds = 300) =>
    request(
      `/mes/finished-logistics/tracking/history/stops?vehicle_id=${encodeURIComponent(vehicleId)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&min_stop_seconds=${encodeURIComponent(minStopSeconds)}`
    ),
  gpsTransportSuggestions: () => request("/gps/suggestions/transports"),
  gpsImportFromTransports: () =>
    request("/gps/import/from-transports", { method: "POST" }),

  mesGetCategories: (includeInactive = false) =>
    request(`/mes/categories?include_inactive=${includeInactive ? "true" : "false"}`),
  mesCreateCategory: (body) =>
    request("/mes/categories", { method: "POST", body: JSON.stringify(body) }),
  mesUpdateCategory: (id, body) =>
    request(`/mes/categories/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  mesDeleteCategory: (id) => request(`/mes/categories/${id}`, { method: "DELETE" }),

  mesGetParts: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/parts?${q.toString()}`);
  },
  mesGetPart: (id) => request(`/mes/parts/${id}`),
  mesCreatePart: (body) =>
    request("/mes/parts", { method: "POST", body: JSON.stringify(body) }),
  mesUpdatePart: (id, body) =>
    request(`/mes/parts/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  mesDeletePart: (id) => request(`/mes/parts/${id}`, { method: "DELETE" }),

  mesGetTemplates: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/templates?${q.toString()}`);
  },
  mesGetTemplate: (id) => request(`/mes/templates/${id}`),
  mesCreateTemplate: (body) =>
    request("/mes/templates", { method: "POST", body: JSON.stringify(body) }),
  mesUpdateTemplate: (id, body) =>
    request(`/mes/templates/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  mesDeleteTemplate: (id) => request(`/mes/templates/${id}`, { method: "DELETE" }),
  mesDuplicateTemplate: (id, code) =>
    request(`/mes/templates/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  mesUploadTemplateImage: async (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/mes/templates/${id}/image`, { method: "POST", body: form });
  },

  mesGetTemplateBom: (templateId) => request(`/mes/templates/${templateId}/bom`),
  mesAddBomLine: (templateId, body) =>
    request(`/mes/templates/${templateId}/bom`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mesUpdateBomLine: (templateId, lineId, body) =>
    request(`/mes/templates/${templateId}/bom/${lineId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesDeleteBomLine: (templateId, lineId) =>
    request(`/mes/templates/${templateId}/bom/${lineId}`, { method: "DELETE" }),
  mesReorderBomLines: (templateId, lines) =>
    request(`/mes/templates/${templateId}/bom/reorder`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),
  mesGetTemplateYigish: (templateId) =>
    request(`/mes/templates/${templateId}/yigish`),

  mesAddYigishLine: (templateId, body) =>
    request(`/mes/templates/${templateId}/yigish`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  mesUpdateYigishLine: (templateId, lineId, body) =>
    request(`/mes/templates/${templateId}/yigish/${lineId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  mesDeleteYigishLine: (templateId, lineId) =>
    request(`/mes/templates/${templateId}/yigish/${lineId}`, {
      method: "DELETE",
    }),

  mesReorderYigishLines: (templateId, lines) =>
    request(`/mes/templates/${templateId}/yigish/reorder`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),

  mesUploadBomDrawing: async (templateId, lineId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/mes/templates/${templateId}/bom/${lineId}/drawing`, {
      method: "POST",
      body: form,
    });
  },

  mesGetBrigades: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/brigades${q.toString() ? `?${q.toString()}` : ""}`);
  },
  mesGetBrigadeUsers: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/brigades/users${q.toString() ? `?${q.toString()}` : ""}`);
  },
  mesCreateBrigade: (body) =>
    request("/mes/brigades", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mesUpdateBrigade: (id, body) =>
    request(`/mes/brigades/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesSetBrigadeStatus: (id, is_active) =>
    request(`/mes/brigades/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ is_active: Boolean(is_active) }),
    }),

  mesGetStages: (includeInactive = false) =>
    request(`/mes/stages?include_inactive=${includeInactive ? "true" : "false"}`),
  mesCreateStage: (body) =>
    request("/mes/stages", { method: "POST", body: JSON.stringify(body) }),
  mesUpdateStage: (id, body) =>
    request(`/mes/stages/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  mesDeleteStage: (id) => request(`/mes/stages/${id}`, { method: "DELETE" }),

  mesGetTemplateRoutes: (templateId) => request(`/mes/templates/${templateId}/routes`),
  mesGetTemplateRoute: (templateId, routeId) =>
    request(`/mes/templates/${templateId}/routes/${routeId}`),
  mesCreateTemplateRoute: (templateId, body) =>
    request(`/mes/templates/${templateId}/routes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mesUpdateTemplateRoute: (templateId, routeId, body) =>
    request(`/mes/templates/${templateId}/routes/${routeId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesDeleteTemplateRoute: (templateId, routeId) =>
    request(`/mes/templates/${templateId}/routes/${routeId}`, { method: "DELETE" }),
  mesSetDefaultRoute: (templateId, routeId) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/set-default`, {
      method: "POST",
    }),
  mesCreateRouteVersion: (templateId, routeId) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/new-version`, {
      method: "POST",
    }),
  mesAddRouteStep: (templateId, routeId, body) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/steps`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mesUpdateRouteStep: (templateId, routeId, stepId, body) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/steps/${stepId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesDeleteRouteStep: (templateId, routeId, stepId) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/steps/${stepId}`, {
      method: "DELETE",
    }),
  mesReorderRouteSteps: (templateId, routeId, steps) =>
    request(`/mes/templates/${templateId}/routes/${routeId}/steps/reorder`, {
      method: "PUT",
      body: JSON.stringify({ steps }),
    }),

  mesGetTemplateDrawings: (templateId) => request(`/mes/templates/${templateId}/drawings`),
  mesUploadDrawing: async (templateId, file, { title = "", revision = "A", is_primary = false } = {}) => {
    const form = new FormData();
    form.append("file", file);
    const q = new URLSearchParams();
    if (title) q.set("title", title);
    q.set("revision", revision || "A");
    if (is_primary) q.set("is_primary", "true");
    return request(`/mes/templates/${templateId}/drawings?${q.toString()}`, {
      method: "POST",
      body: form,
    });
  },
  mesUpdateDrawing: (templateId, drawingId, body) =>
    request(`/mes/templates/${templateId}/drawings/${drawingId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesSetPrimaryDrawing: (templateId, drawingId) =>
    request(`/mes/templates/${templateId}/drawings/${drawingId}/set-primary`, {
      method: "POST",
    }),
  mesDeleteDrawing: (templateId, drawingId) =>
    request(`/mes/templates/${templateId}/drawings/${drawingId}`, { method: "DELETE" }),

  mesGetJobs: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/jobs?${q.toString()}`);
  },
  mesGetJob: (id) => request(`/mes/jobs/${id}`),
  mesCreateJob: (body) =>
    request("/mes/jobs", { method: "POST", body: JSON.stringify(body) }),
  mesUpdateJob: (id, body) =>
    request(`/mes/jobs/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  mesReleaseJob: (id) => request(`/mes/jobs/${id}/release`, { method: "POST" }),
  mesUpdateJobStatus: (id, status) =>
    request(`/mes/jobs/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),

  mesLazerQueue: () => request("/mes/terminal/lazer/queue"),
  mesLazerJob: (id) => request(`/mes/terminal/lazer/jobs/${id}`),
  mesLazerAcceptJob: (id) =>
    request(`/mes/terminal/lazer/jobs/${id}/accept`, { method: "POST" }),
  mesLazerStartJob: (id) =>
    request(`/mes/terminal/lazer/jobs/${id}/start`, { method: "POST" }),
  mesLazerCompleteJob: (id) =>
    request(`/mes/terminal/lazer/jobs/${id}/complete`, { method: "POST" }),
  mesLazerUpdateQuantities: (id, lines) =>
    request(`/mes/terminal/lazer/jobs/${id}/quantities`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),
  warehouseDetailStock: (params = {}) => request(`/warehouse/stock?${new URLSearchParams(params).toString()}`),
  warehouseDetailTransactions: (params = {}) => request(`/warehouse/transactions?${new URLSearchParams(params).toString()}`),
  warehouseDetailStockIn: (jobId, bomLineId, quantity) => request(`/warehouse/stock/in?job_id=${jobId}&bom_line_id=${bomLineId}&quantity=${quantity}`, { method: "POST" }),
  warehouseDetailStockAction: (action, params) => request(`/warehouse/stock/${action}?${new URLSearchParams(params).toString()}`, { method: "POST" }),

  mesYigishQueue: () => request("/mes/terminal/yigish/queue"),
  mesYigishBrigade: () => request("/mes/terminal/yigish/brigade"),
  mesYigishJob: (id) => request(`/mes/terminal/yigish/jobs/${id}`),
  mesYigishAcceptJob: (id) =>
    request(`/mes/terminal/yigish/jobs/${id}/accept`, { method: "POST" }),
  mesYigishStartJob: (id) =>
    request(`/mes/terminal/yigish/jobs/${id}/start`, { method: "POST" }),
  mesYigishCompleteJob: (id, workerUserIds = []) =>
    request(`/mes/terminal/yigish/jobs/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({
        worker_user_ids: workerUserIds,
      }),
    }),
  mesYigishUpdateQuantities: (id, lines) =>
    request(`/mes/terminal/yigish/jobs/${id}/quantities`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),

  mesSvarshikDashboard: () => request("/mes/terminal/svarshik/dashboard"),
  mesSvarshikQueue: () => request("/mes/terminal/svarshik/queue"),
  mesSvarshikJob: (id) => request(`/mes/terminal/svarshik/jobs/${id}`),
  mesSvarshikAcceptJob: (id) =>
    request(`/mes/terminal/svarshik/jobs/${id}/accept`, { method: "POST" }),
  mesSvarshikStartJob: (id) =>
    request(`/mes/terminal/svarshik/jobs/${id}/start`, { method: "POST" }),
  mesSvarshikCompleteJob: (id) =>
    request(`/mes/terminal/svarshik/jobs/${id}/complete`, { method: "POST" }),
  mesSvarshikUpdateQuantities: (id, lines) =>
    request(`/mes/terminal/svarshik/jobs/${id}/quantities`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),

  mesMonitorDashboard: () => request("/mes/monitor/dashboard"),
  mesMonitorJobs: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) q.set(k, String(v));
    });
    return request(`/mes/monitor/jobs?${q.toString()}`);
  },

  mesKraskaDashboard: () => request("/mes/terminal/kraska/dashboard"),
  mesKraskaQueue: () => request("/mes/terminal/kraska/queue"),
  mesKraskaJob: (id) => request(`/mes/terminal/kraska/jobs/${id}`),
  mesKraskaAcceptJob: (id) =>
    request(`/mes/terminal/kraska/jobs/${id}/accept`, { method: "POST" }),
  mesKraskaStartJob: (id) =>
    request(`/mes/terminal/kraska/jobs/${id}/start`, { method: "POST" }),
  mesKraskaSendToDrying: (id) =>
    request(`/mes/terminal/kraska/jobs/${id}/drying`, { method: "POST" }),
  mesKraskaCompleteJob: (id) =>
    request(`/mes/terminal/kraska/jobs/${id}/complete`, { method: "POST" }),
  mesKraskaUpdatePaintMetadata: (id, body) =>
    request(`/mes/terminal/kraska/jobs/${id}/paint-metadata`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesKraskaUpdateQuantities: (id, lines) =>
    request(`/mes/terminal/kraska/jobs/${id}/quantities`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),

  mesQcDashboard: () => request("/mes/terminal/qc/dashboard"),
  mesQcQueue: () => request("/mes/terminal/qc/queue"),
  mesQcReworkQueue: () => request("/mes/terminal/qc/rework-queue"),
  mesQcRejectionReasons: () => request("/mes/terminal/qc/rejection-reasons"),
  mesQcJob: (id) => request(`/mes/terminal/qc/jobs/${id}`),
  mesQcAcceptJob: (id) =>
    request(`/mes/terminal/qc/jobs/${id}/accept`, { method: "POST" }),
  mesQcStartJob: (id) =>
    request(`/mes/terminal/qc/jobs/${id}/start`, { method: "POST" }),
  mesQcCompleteJob: (id) =>
    request(`/mes/terminal/qc/jobs/${id}/complete`, { method: "POST" }),
  mesQcUpdateQuantities: (id, lines) =>
    request(`/mes/terminal/qc/jobs/${id}/quantities`, {
      method: "PUT",
      body: JSON.stringify({ lines }),
    }),
  mesQcCreateRework: (id, body) =>
    request(`/mes/terminal/qc/jobs/${id}/rework`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mesQcStartRework: (reworkId) =>
    request(`/mes/terminal/qc/rework/${reworkId}/start`, { method: "POST" }),
  mesQcCompleteRework: (reworkId) =>
    request(`/mes/terminal/qc/rework/${reworkId}/complete`, { method: "POST" }),
  mesQcAdminRejectionReasons: (includeInactive = false) =>
    request(`/mes/qc/rejection-reasons?include_inactive=${includeInactive ? "true" : "false"}`),
  mesQcAdminCreateRejectionReason: (body) =>
    request("/mes/qc/rejection-reasons", { method: "POST", body: JSON.stringify(body) }),
  mesQcAdminUpdateRejectionReason: (id, body) =>
    request(`/mes/qc/rejection-reasons/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  mesPackagingDashboard: () => request("/mes/terminal/packaging/dashboard"),
  mesPackagingQueue: () => request("/mes/terminal/packaging/queue"),
  mesPackagingJob: (id) => request(`/mes/terminal/packaging/jobs/${id}`),
  mesPackagingAcceptJob: (id) =>
    request(`/mes/terminal/packaging/jobs/${id}/accept`, { method: "POST" }),
  mesPackagingStartJob: (id) =>
    request(`/mes/terminal/packaging/jobs/${id}/start`, { method: "POST" }),
  mesPackagingCompleteJob: (id) =>
    request(`/mes/terminal/packaging/jobs/${id}/complete`, { method: "POST" }),
  mesPackagingUpdateData: (id, body) =>
    request(`/mes/terminal/packaging/jobs/${id}/packaging-data`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  mesWarehouseDashboard: () => request("/mes/terminal/warehouse/dashboard"),
  mesWarehouseQueue: () => request("/mes/terminal/warehouse/queue"),
  mesWarehouseInventory: (detailed = false) => request(`/mes/terminal/warehouse/inventory${detailed ? "?detailed=true" : ""}`),
  mesWarehouseLocations: () => request("/mes/terminal/warehouse/locations"),
  mesWarehouseJob: (id) => request(`/mes/terminal/warehouse/jobs/${id}`),
  mesWarehouseAcceptReceipt: (id) =>
    request(`/mes/terminal/warehouse/jobs/${id}/accept`, { method: "POST" }),
  mesWarehouseStartPlacement: (id) =>
    request(`/mes/terminal/warehouse/jobs/${id}/start`, { method: "POST" }),
  mesWarehouseCompleteReceipt: (id) =>
    request(`/mes/terminal/warehouse/jobs/${id}/complete`, { method: "POST" }),
  mesWarehousePlacePackage: (jobId, packageId, locationId) =>
    request(`/mes/terminal/warehouse/jobs/${jobId}/packages/${packageId}/place`, {
      method: "POST",
      body: JSON.stringify({ location_id: locationId }),
    }),
  mesWarehouseAdminLocations: (includeInactive = false) =>
    request(`/mes/warehouse/locations?include_inactive=${includeInactive ? "true" : "false"}`),
  mesWarehouseAdminCreateLocation: (body) =>
    request("/mes/warehouse/locations", { method: "POST", body: JSON.stringify(body) }),
  mesWarehouseAdminUpdateLocation: (id, body) =>
    request(`/mes/warehouse/locations/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  mesDispatchDashboard: () => request("/mes/terminal/dispatch/dashboard"),
  mesDispatchQueue: () => request("/mes/terminal/dispatch/queue"),
  mesDispatchJob: (id) => request(`/mes/terminal/dispatch/jobs/${id}`),
  mesDispatchAccept: (id) =>
    request(`/mes/terminal/dispatch/jobs/${id}/accept`, { method: "POST" }),
  mesDispatchStartLoading: (id) =>
    request(`/mes/terminal/dispatch/jobs/${id}/start`, { method: "POST" }),
  mesDispatchUpdateTransport: (id, body) =>
    request(`/mes/terminal/dispatch/jobs/${id}/transport`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  mesDispatchLoadPackage: (jobId, packageId) =>
    request(`/mes/terminal/dispatch/jobs/${jobId}/packages/${packageId}/load`, {
      method: "POST",
    }),
  mesDispatchShip: (id) =>
    request(`/mes/terminal/dispatch/jobs/${id}/ship`, { method: "POST" }),
  mesDispatchDeliver: (id) =>
    request(`/mes/terminal/dispatch/jobs/${id}/deliver`, { method: "POST" }),

  materialsDashboard: () => request("/materials/dashboard"),
  materialsCategories: (includeInactive = false) =>
    request(`/materials/categories?include_inactive=${includeInactive ? "true" : "false"}`),
  materialsCreateCategory: (body) =>
    request("/materials/categories", { method: "POST", body: JSON.stringify(body) }),
  materialsUpdateCategory: (id, body) =>
    request(`/materials/categories/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  materialsItems: (includeInactive = false) =>
    request(`/materials/items?include_inactive=${includeInactive ? "true" : "false"}`),
  materialsGetItem: (id) => request(`/materials/items/${id}`),
  materialsCodePreview: (params) =>
    request(`/materials/code-preview?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null))}`),
  materialsCreateItem: (body) =>
    request("/materials/items", { method: "POST", body: JSON.stringify(body) }),
  materialsUpdateItem: (id, body) =>
    request(`/materials/items/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  materialsUploadImage: async (id, file) => {
    const form = new FormData();
    form.append("file", file, file.name);
    const data = await request(`/materials/items/${id}/image`, {
      method: "POST",
      body: form,
    });
    return {
      ...data,
      image_url: uploadUrl(data?.image_url),
    };
  },
  materialsReceipts: (limit = 100) => request(`/materials/receipts?limit=${limit}`),
  materialsReceipt: (id) => request(`/materials/receipts/${id}`),
  materialsCreateReceipt: (body) =>
    request("/materials/receipts", { method: "POST", body: JSON.stringify(body) }),
  materialsUpdateReceipt: (id, body) =>
    request(`/materials/receipts/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  materialsConfirmReceipt: (id, body) =>
    request(`/materials/receipts/${id}/confirm`, { method: "POST", body: JSON.stringify(body) }),
  materialsReverseReceipt: (id, body) =>
    request(`/materials/receipts/${id}/reverse`, { method: "POST", body: JSON.stringify(body) }),
  materialsIssues: (limit = 100) => request(`/materials/issues?limit=${limit}`),
  materialsCreateIssue: (body) =>
    request("/materials/issues", { method: "POST", body: JSON.stringify(body) }),
  materialPhysicalPieces: (materialId = "") => request(`/materials/physical-pieces${materialId ? `?material_id=${materialId}` : ""}`),
  materialPhysicalIssues: () => request("/materials/physical-issues"),
  materialCreatePhysicalIssue: (body) => request("/materials/physical-issues", { method: "POST", body: JSON.stringify(body) }),
  materialReservePiece: (id, body) => request(`/materials/physical-issues/${id}/reserve`, { method: "POST", body: JSON.stringify(body) }),
  materialReleasePieces: (id) => request(`/materials/physical-issues/${id}/release`, { method: "POST" }),
  materialIssueReserved: (id) => request(`/materials/physical-issues/${id}/issue`, { method: "POST" }),
  materialRecordCut: (id, body) => request(`/materials/physical-issues/${id}/cuts`, { method: "POST", body: JSON.stringify(body) }),
  materialCutRecommendation: (body) => request("/materials/cutting/recommend", { method: "POST", body: JSON.stringify(body) }),
  materialCuttingContext: () => request("/materials/cutting/context"),
  materialJobRequirements: (jobId) => request(`/materials/cutting/jobs/${jobId}/requirements`),
  materialCreateIssueFromRequirement: (body) => request("/materials/cutting/issues", { method: "POST", body: JSON.stringify(body) }),
  materialsAdjustments: (limit = 100) => request(`/materials/adjustments?limit=${limit}`),
  materialsCreateAdjustment: (body) =>
    request("/materials/adjustments", { method: "POST", body: JSON.stringify(body) }),
  materialsMovements: (limit = 200) => request(`/materials/movements?limit=${limit}`),

  materialsPlanningShortages: () => request("/materials/planning/shortages"),
  materialsPlanningParts: () => request("/materials/planning/parts"),
  materialsJobReservations: (jobId) => request(`/materials/jobs/${jobId}/reservations`),
  materialsPartBom: (partId, includeInactive = false) =>
    request(`/materials/parts/${partId}/bom?include_inactive=${includeInactive ? "true" : "false"}`),
  materialsAddPartBomLine: (partId, body) =>
    request(`/materials/parts/${partId}/bom`, { method: "POST", body: JSON.stringify(body) }),
  materialsUpdatePartBomLine: (partId, lineId, body) =>
    request(`/materials/parts/${partId}/bom/${lineId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  materialsDeletePartBomLine: (partId, lineId) =>
    request(`/materials/parts/${partId}/bom/${lineId}`, { method: "DELETE" }),

  materialsConsumptionRules: (includeInactive = false) =>
    request(`/materials/consumption-rules?include_inactive=${includeInactive ? "true" : "false"}`),
  materialsCreateConsumptionRule: (body) =>
    request("/materials/consumption-rules", { method: "POST", body: JSON.stringify(body) }),
  materialsUpdateConsumptionRule: (id, body) =>
    request(`/materials/consumption-rules/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  materialsConsumptionsToday: (limit = 100) =>
    request(`/materials/consumptions/today?limit=${limit}`),
  materialsJobConsumptions: (jobId) => request(`/materials/jobs/${jobId}/consumptions`),
  materialsJobMaterialCost: (jobId) => request(`/materials/jobs/${jobId}/material-cost`),

  getTelegramStatus: () => request("/telegram/status"),
  generateTelegramLinkCode: () =>
    request("/telegram/link-code", { method: "POST" }),
  verifyTelegramLink: (body) =>
    request("/telegram/verify-link", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  unlinkTelegram: () => request("/telegram/unlink", { method: "POST" }),
  adminSetUserTelegram: (userId, body) =>
    request(`/telegram/admin/users/${userId}/telegram`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  adminMigrationExport: async (body) => {
    const tokens = getStoredTokens();
    const res = await fetch(`${API_BASE}/admin/migration/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokens?.access_token || ""}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText || "Export failed");
    }
    const reportHeader = res.headers.get("X-Migration-Export-Report");
    let exportReport = null;
    if (reportHeader) {
      try {
        exportReport = JSON.parse(reportHeader);
      } catch {
        exportReport = null;
      }
    }
    const blob = await res.blob();
    return { blob, exportReport };
  },

  adminMigrationPreview: async (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/admin/migration/preview", { method: "POST", body: form });
  },

  adminMigrationImport: async (file, adminPassword) => {
    const form = new FormData();
    form.append("file", file);
    form.append("admin_password", adminPassword);
    form.append("confirm", "true");
    return request("/admin/migration/import", { method: "POST", body: form });
  },

  adminMigrationHistory: () => request("/admin/migration/history"),

  traceabilityDashboard: () => request("/traceability/dashboard"),
  packagePassport: (labelCode) =>
    request(`/packages/${encodeURIComponent(labelCode)}`),
  packageAssignLocation: (labelCode, body) =>
    request(`/packages/${encodeURIComponent(labelCode)}/location`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  publicPackageTrack: (labelCode) =>
    request(`/track/package/${encodeURIComponent(labelCode)}`),
  mesDispatchScanLabel: (jobId, labelCode) =>
    request(`/mes/terminal/dispatch/jobs/${jobId}/scan-label`, {
      method: "POST",
      body: JSON.stringify({ label_code: labelCode }),
    }),
  adminGetLabelPrinters: () => request("/admin/settings/label-printers"),
  adminSaveLabelPrinters: (printers) =>
    request("/admin/settings/label-printers", {
      method: "PUT",
      body: JSON.stringify({ printers }),
    }),
  adminPrintingDashboard: () => request("/admin/printing/dashboard"),
  packageReprintLabel: (labelCode) =>
    request(`/packages/${encodeURIComponent(labelCode)}/reprint`, { method: "POST" }),
  adminRetryPrintJob: (jobId) =>
    request(`/printing/jobs/${jobId}/retry`, { method: "POST" }),

  adminMigrationRollback: async (migrationId, adminPassword) => {
    const form = new FormData();
    form.append("admin_password", adminPassword);
    return request(`/admin/migration/rollback/${migrationId}`, {
      method: "POST",
      body: form,
    });
  },

  productionProjects: (params = {}) => request(`/production-projects?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null))}`),
  productionProject: (id) => request(`/production-projects/${id}`),
  productionProjectCreate: (body) => request("/production-projects", { method: "POST", body: JSON.stringify(body) }),
  productionProjectUpdate: (id, body) => request(`/production-projects/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  productionProjectAddLine: (id, body) => request(`/production-projects/${id}/lines`, { method: "POST", body: JSON.stringify(body) }),
  productionProjectUpdateLine: (id, lineId, body) => request(`/production-projects/${id}/lines/${lineId}`, { method: "PUT", body: JSON.stringify(body) }),
  productionProjectRemoveLine: (id, lineId) => request(`/production-projects/${id}/lines/${lineId}`, { method: "DELETE" }),
  productionProjectMergeLine: (id, body) => request(`/production-projects/${id}/lines/merge`, { method: "POST", body: JSON.stringify(body) }),
  productionProjectPreview: (id, signal) =>
    request(`/production-projects/${id}/requirements/preview`, { signal }),
  productionProjectRequirements: (id) => request(`/production-projects/${id}/requirements`),
  productionProjectProgress: (id) => request(`/production-projects/${id}/progress`),
  productionProjectForecast: (id) => request(`/production-projects/${id}/forecast`),
  productionProjectRelease: (id, body) => request(`/production-projects/${id}/release`, { method: "POST", body: JSON.stringify(body) }),
  productionProjectCancel: (id, body) => request(`/production-projects/${id}/cancel`, { method: "POST", body: JSON.stringify(body) }),
  productionProjectClone: (id, code) => request(`/production-projects/${id}/clone?project_code=${encodeURIComponent(code)}`, { method: "POST" }),
  productionJobStageReturn: (id, body) => request(`/production-projects/jobs/${id}/stage-return`, { method: "POST", body: JSON.stringify(body) }),
  productionJobStageReopen: (id, body) => request(`/production-projects/jobs/${id}/stage-reopen`, { method: "POST", body: JSON.stringify(body) }),
  productionJobPaintReconcile: (id, body) => request(`/production-projects/jobs/${id}/paint-reconciliation`, { method: "POST", body: JSON.stringify(body) }),
  productionJobCorrectionHistory: (id) => request(`/production-projects/jobs/${id}/correction-history`),

  finishedLocations: (includeInactive = false) => request(`/mes/finished-logistics/locations?include_inactive=${includeInactive}`),
  finishedLocationCreate: (body) => request("/mes/finished-logistics/locations", { method: "POST", body: JSON.stringify(body) }),
  finishedWarehouseTotals: (projectId = "") => request(`/mes/finished-logistics/warehouse-totals${projectId ? `?project_id=${projectId}` : ""}`),
  finishedPlacements: (params = {}) => request(`/mes/finished-logistics/placements?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null))}`),
  finishedVehicles: (includeInactive = false) => request(`/mes/finished-logistics/vehicles?include_inactive=${includeInactive}`),
  finishedDrivers: (includeInactive = false) => request(`/mes/finished-logistics/drivers?include_inactive=${includeInactive}`),
  driverMe: () => request("/mes/finished-logistics/driver/me"),
  driverTasks: (status = "") =>
    request(status ? `/driver/tasks?status=${encodeURIComponent(status)}` : "/driver/tasks"),

  driverTaskPickup: (id, location = {}) =>
    request(`/driver/tasks/${id}/pickup`, {
      method: "POST",
      body: JSON.stringify({
        latitude: location.latitude,
        longitude: location.longitude,
        address: location.address || "",
      }),
    }),

  driverTaskDeliver: (id, form) =>
    request(`/driver/tasks/${id}/deliver`, {
      method: "POST",
      body: form,
    }),

  driverTaskComplete: (id, form) =>
    request(`/driver/tasks/${id}/complete`, {
      method: "POST",
      body: form,
    }),
  finishedVehicleCreate: (body) => request("/mes/finished-logistics/vehicles", { method: "POST", body: JSON.stringify(body) }),
  finishedVehicleUpdate: (id, body) => request(`/mes/finished-logistics/vehicles/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  finishedVehicleStateUpdate: (id, body) => request(`/mes/finished-logistics/vehicles/${id}/operational-state`, { method: "PUT", body: JSON.stringify(body) }),
  finishedDriverCreate: (body) => request("/mes/finished-logistics/drivers", { method: "POST", body: JSON.stringify(body) }),
  finishedDriverUpdate: (id, body) => request(`/mes/finished-logistics/drivers/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  finishedDriverStatus: (id, body) => request(`/mes/finished-logistics/drivers/${id}/status`, { method: "POST", body: JSON.stringify(body) }),
  finishedGpsDevices: (includeInactive = false) => request(`/mes/finished-logistics/gps-devices?include_inactive=${includeInactive}`),
  finishedGpsDeviceCreate: (body) => request("/mes/finished-logistics/gps-devices", { method: "POST", body: JSON.stringify(body) }),
  finishedGpsDeviceUpdate: (id, body) => request(`/mes/finished-logistics/gps-devices/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  finishedGpsDeviceUnbind: (id, body) => request(`/mes/finished-logistics/gps-devices/${id}/unbind`, { method: "POST", body: JSON.stringify(body) }),
  finishedTrips: (params = {}) => { const qs = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null)).toString(); return request(`/mes/finished-logistics/trips${qs ? `?${qs}` : ""}`); },
  finishedTrip: (id) => request(`/mes/finished-logistics/trips/${id}`),
  finishedTripCreate: (body) => request("/mes/finished-logistics/trips", { method: "POST", body: JSON.stringify(body) }),
  finishedConsolidatedTripCreate: (body) => request("/mes/finished-logistics/trips/consolidated", { method: "POST", body: JSON.stringify(body) }),
  finishedReadyCargo: () => request("/mes/finished-logistics/ready-for-logistics"),
  finishedTripTransition: (id, body) => request(`/mes/finished-logistics/trips/${id}/transition`, { method: "POST", body: JSON.stringify(body) }),
  finishedTripAssignmentUpdate: (id, body) => request(`/mes/finished-logistics/trips/${id}/assignment`, { method: "PUT", body: JSON.stringify(body) }),
  finishedTripPlanningUpdate: (id, body) => request(`/mes/finished-logistics/trips/${id}/planning`, { method: "PUT", body: JSON.stringify(body) }),
  finishedTripRoute: (id) => request(`/mes/finished-logistics/trips/${id}/route`),
  finishedTripRouteCreate: (id, body) => request(`/mes/finished-logistics/trips/${id}/route`, { method: "POST", body: JSON.stringify(body) }),
  finishedTripRouteUpdate: (id, body) => request(`/mes/finished-logistics/trips/${id}/route`, { method: "PUT", body: JSON.stringify(body) }),
  finishedTripRouteStatus: (id, body) => request(`/mes/finished-logistics/trips/${id}/route/status`, { method: "POST", body: JSON.stringify(body) }),
  finishedTripRouteCancel: (id, version) => request(`/mes/finished-logistics/trips/${id}/route?expected_version=${version}`, { method: "DELETE" }),
  finishedTripRouteStopCreate: (id, body) => request(`/mes/finished-logistics/trips/${id}/route/stops`, { method: "POST", body: JSON.stringify(body) }),
  finishedTripRouteStopUpdate: (id, stopId, body) => request(`/mes/finished-logistics/trips/${id}/route/stops/${stopId}`, { method: "PUT", body: JSON.stringify(body) }),
  finishedTripRouteStopDelete: (id, stopId, version) => request(`/mes/finished-logistics/trips/${id}/route/stops/${stopId}?expected_version=${version}`, { method: "DELETE" }),
  finishedTripRouteStopsReorder: (id, body) => request(`/mes/finished-logistics/trips/${id}/route/stops/reorder`, { method: "POST", body: JSON.stringify(body) }),
  finishedLogisticsAlerts: () => request("/mes/finished-logistics/alerts"),
  finishedTripAssign: (id, body) => request(`/mes/finished-logistics/trips/${id}/shipment-items`, { method: "POST", body: JSON.stringify(body) }),
  finishedTripProgress: (id) => request(`/mes/finished-logistics/trips/${id}/progress`),
  finishedLoadingPlan: (id) => request(`/mes/finished-logistics/trips/${id}/loading-plan`),
  finishedLoadingPlanSave: (id, placements) => request(`/mes/finished-logistics/trips/${id}/loading-plan`, { method: "PUT", body: JSON.stringify({ placements }) }),
  finishedLoadingPlanAutomatic: (id) => request(`/mes/finished-logistics/trips/${id}/loading-plan/automatic`, { method: "POST" }),
  finishedLoadingPlanValidate: (id) => request(`/mes/finished-logistics/trips/${id}/loading-plan/validate`, { method: "POST" }),
  finishedConfirmLoading: (id, body) => request(`/mes/finished-logistics/trips/${id}/confirm-loading`, { method: "POST", body: JSON.stringify(body) }),
  finishedDispatch: (id, body) => request(`/mes/finished-logistics/trips/${id}/dispatch`, { method: "POST", body: JSON.stringify(body) }),
  finishedArrival: (id, body) => request(`/mes/finished-logistics/trips/${id}/arrival`, { method: "POST", body: JSON.stringify(body) }),
  finishedDelivery: (id, body) => request(`/mes/finished-logistics/trips/${id}/delivery`, { method: "POST", body: JSON.stringify(body) }),
  finishedAcceptance: (id, body) => request(`/mes/finished-logistics/trips/${id}/acceptance`, { method: "POST", body: JSON.stringify(body) }),
  finishedUnload: (id, itemId, body) => request(`/mes/finished-logistics/trips/${id}/shipment-items/${itemId}/unload`, { method: "POST", body: JSON.stringify(body) }),
  finishedReturnToWarehouse: (id, itemId, body) => request(`/mes/finished-logistics/trips/${id}/shipment-items/${itemId}/return-to-warehouse`, { method: "POST", body: JSON.stringify(body) }),
  finishedReload: (id, itemId, body) => request(`/mes/finished-logistics/trips/${id}/shipment-items/${itemId}/reload`, { method: "POST", body: JSON.stringify(body) }),
  finishedTransfer: (id, itemId, body) => request(`/mes/finished-logistics/trips/${id}/shipment-items/${itemId}/transfer`, { method: "POST", body: JSON.stringify(body) }),
  finishedEvidence: (id) => request(`/mes/finished-logistics/trips/${id}/evidence`),
  finishedEvidenceUpload: (id, form) => request(`/mes/finished-logistics/trips/${id}/evidence`, { method: "POST", body: form }),
  finishedTripTracking: (id, limit = 500) => request(`/mes/finished-logistics/trips/${id}/tracking?limit=${limit}`),
  finishedTripDocuments: (id) => request(`/mes/finished-logistics/trips/${id}/documents`),
  finishedTripDocumentCreate: (id, body) => request(`/mes/finished-logistics/trips/${id}/documents`, { method: "POST", body: JSON.stringify(body) }),
  finishedTrackingFleet: (params = {}) => { const qs = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value != null)).toString(); return request(`/mes/finished-logistics/tracking/fleet${qs ? `?${qs}` : ""}`); },
};

export async function apiDownload(path, filename) {
  const res = await authenticatedFetch(path);
  if (!res.ok) {
    throw new Error(`Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename || "download";
  a.click();
  URL.revokeObjectURL(a.href);
}


