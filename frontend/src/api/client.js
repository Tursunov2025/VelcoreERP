const RAW_API_BASE =
  import.meta.env.VITE_API_URL || "https://azmus-crm.onrender.com";

// Strip any trailing slash so `${API_BASE}${path}` never produces a double slash.
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");

if (import.meta.env.DEV) {
  // Helps diagnose "Not Found" issues caused by hitting the wrong backend.
  console.info(`[api] base URL = ${API_BASE}`);
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
  const tokens = getStoredTokens();
  const headers = { ...options.headers };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (tokens?.access_token) {
    headers.Authorization = `Bearer ${tokens.access_token}`;
  }

  const method = options.method || "GET";
  const url = `${API_BASE}${path}`;

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (networkErr) {
    console.error(`[api] ${method} ${url} — network error:`, networkErr);
    throw new Error(
      `Server bilan bog'lanib bo'lmadi (${API_BASE}). Backend ishlayotganini tekshiring.`
    );
  }

  if (response.status === 401 && retry && tokens?.refresh_token) {
    const newToken = await refreshAccessToken();
    if (newToken) return request(path, options, false);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      data?.error ||
      data?.detail ||
      (Array.isArray(data?.detail) ? data.detail[0]?.msg : null) ||
      response.statusText;

    if (response.status === 404) {
      console.error(
        `[api] ${method} ${url} → 404 Not Found. ` +
          `Tekshiring: VITE_API_URL (${API_BASE}) shu route mavjud bo'lgan backendga ishora qilyaptimi?`
      );
    } else {
      console.error(`[api] ${method} ${url} → ${response.status}`, data);
    }

    throw new Error(message || "Request failed");
  }

  if (data?.error) throw new Error(data.error);
  return data;
}

export function uploadUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export const api = {
  login: (body) =>
    fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");
      return data;
    }),

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
    const q = new URLSearchParams();
    if (title) q.set("title", title);
    if (description) q.set("description", description);
    if (folder_id != null && folder_id !== "") q.set("folder_id", String(folder_id));
    q.set("is_important", is_important ? "true" : "false");
    return request(`/llp/documents?${q.toString()}`, { method: "POST", body: form });
  },
  llpUpdateDocument: (id, body) =>
    request(`/llp/documents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  llpDeleteDocument: (id) => request(`/llp/documents/${id}`, { method: "DELETE" }),
  llpMarkRead: (id) => request(`/llp/documents/${id}/read`, { method: "POST" }),

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
  mesUploadBomDrawing: async (templateId, lineId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/mes/templates/${templateId}/bom/${lineId}/drawing`, {
      method: "POST",
      body: form,
    });
  },

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
  mesWarehouseInventory: () => request("/mes/terminal/warehouse/inventory"),
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
  materialsCreateItem: (body) =>
    request("/materials/items", { method: "POST", body: JSON.stringify(body) }),
  materialsUpdateItem: (id, body) =>
    request(`/materials/items/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  materialsReceipts: (limit = 100) => request(`/materials/receipts?limit=${limit}`),
  materialsCreateReceipt: (body) =>
    request("/materials/receipts", { method: "POST", body: JSON.stringify(body) }),
  materialsIssues: (limit = 100) => request(`/materials/issues?limit=${limit}`),
  materialsCreateIssue: (body) =>
    request("/materials/issues", { method: "POST", body: JSON.stringify(body) }),
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

  adminMigrationRollback: async (migrationId, adminPassword) => {
    const form = new FormData();
    form.append("admin_password", adminPassword);
    return request(`/admin/migration/rollback/${migrationId}`, {
      method: "POST",
      body: form,
    });
  },
};

export { API_BASE };
