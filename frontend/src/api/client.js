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
    request("/admin/settings/system", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  adminGetOnlineUsers: () => request("/admin/operators/online"),
  adminGetAuditLogs: () => request("/admin/audit-logs"),

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
};

export { API_BASE };
