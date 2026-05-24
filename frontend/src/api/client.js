const API_BASE =
  import.meta.env.VITE_API_URL || "https://azmus-crm.onrender.com";

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

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

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
};

export { API_BASE };
